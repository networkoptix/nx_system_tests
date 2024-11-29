# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import re
import shutil
import time
from contextlib import AbstractContextManager
from contextlib import ExitStack
from contextlib import contextmanager
from fnmatch import fnmatch
from pathlib import Path
from typing import Any
from typing import Collection
from typing import Mapping
from typing import NamedTuple
from typing import Optional
from typing import Sequence
from uuid import UUID

from _internal.service_registry import default_prerequisite_store
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from installation import Mediaserver
from mediaserver_api import BaseCamera
from mediaserver_api import CameraStatus
from mediaserver_api import EventCondition
from mediaserver_api import EventNotOccurred
from mediaserver_api import EventState
from mediaserver_api import EventType
from mediaserver_api import MediaserverApi
from mediaserver_api import RuleAction
from mediaserver_scenarios.license_scenarios import grant_license
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from os_access import WindowsAccess
from tests.analytics.helpers.object_stream import dump_object_stream_to_file
from tests.analytics.helpers.object_stream import load_tracks_from_file
from tests.analytics.helpers.object_stream import make_object_stream_from_tracks
from tests.analytics.helpers.track import Track
from tests.waiting import wait_for_truthy

_logger = logging.getLogger(__name__)


def _enable_leak_detector(mediaserver: Mediaserver):
    # Do not crash on first assert - we will collect them in the end and print all of them. Reason
    # for that is that leak detector is writing asserts to error log and we need to see all of them
    mediaserver.update_ini('nx_utils', {'assertCrash': 0})
    mediaserver.update_ini('vms_server_plugins', {
        'enableRefCountableRegistry': 1,
        'verboseRefCountableRegistry': 1,
        'useServerLogForRefCountableRegistry': 1,
        })


def check_for_plugin_diagnostic_events(api: MediaserverApi):
    # PDE is a common abbreviation for Plugin/Integration Diagnostic Event.
    failure_events = []
    normal_pde_plugin_event_caption_re = re.compile(
        r'(Info|Warning|Error) message from (Engine|DeviceAgent)')
    engine_collection = api.get_analytics_engine_collection()
    pde_plugin = engine_collection.get_stub(
        'Plugin Diagnostic Events', 'Integration Diagnostic Events')
    event_queue = api.event_queue()
    while True:
        try:
            event = event_queue.wait_for_next(timeout_sec=0)
        except EventNotOccurred:
            break
        if event.event_type != EventType.PLUGIN_DIAGNOSTIC_EVENT:
            continue
        if event.resource_id == pde_plugin.id():
            if re.match(normal_pde_plugin_event_caption_re, event.caption):
                continue
        # Normally, engine name is not present in the PDE.
        failure_events.append((
            event, f"Engine name is {engine_collection.get_by_id(event.resource_id).name()}"))
    if failure_events:
        raise RuntimeError(
            f"Found Plugin/Integration Diagnostic Events "
            f"signalizing about a failure: {failure_events}")


class _AttributeNames(NamedTuple):

    internal_stub_settings_name: str
    diagnostic_event_flags_for_engine: Collection[str]
    diagnostic_event_flags_for_agent: Collection[str]


attribute_names = _AttributeNames(
    internal_stub_settings_name='stub_analytics_plugin_nx.stub.settings',
    diagnostic_event_flags_for_engine=(
        'generatePluginDiagnosticEventsFromEngine',
        'generateIntegrationDiagnosticEventsFromEngine',
        ),
    diagnostic_event_flags_for_agent=(
        'generatePluginDiagnosticEventsFromDeviceAgent',
        'generateIntegrationDiagnosticEventsFromDeviceAgent',
        ),
    )


@contextmanager
def recording_camera(mediaserver: Mediaserver) -> AbstractContextManager[BaseCamera]:
    camera_server = MultiPartJpegCameraServer()
    api = mediaserver.api
    [camera] = add_cameras(mediaserver, camera_server)
    api.enable_secondary_stream(camera.id)
    with camera_server.async_serve():
        api.start_recording(camera.id)
        api.wait_for_camera_status(camera.id, CameraStatus.RECORDING)
        yield camera
        api.stop_recording(camera.id)


def set_engine_settings(api: MediaserverApi, engine_id: UUID, new_settings: dict):
    api.set_analytics_engine_settings(engine_id, new_settings)


def add_analytics_event_rule(
        api: MediaserverApi,
        resource_id,
        engine_id: UUID,
        input_port_id: str,
        event_type=EventType.ANALYTICS_SDK,
        ):
    api.add_event_rule(
        event_type=event_type,
        event_state=EventState.UNDEFINED,
        action=RuleAction('showPopupAction', params={'allUsers': True}),
        event_resource_ids=[str(resource_id)],
        event_condition=EventCondition(params={
            'analyticsEngineId': str(engine_id),
            'allUsers': True,
            'inputPortId': input_port_id,
            }),
        )


def compare_settings_dicts(new: Mapping, current: Mapping) -> Collection[str]:
    errors = []
    for k, v in new.items():
        if k not in current:
            errors.append(f"{k} is not in current settings")
        elif current[k] != v:
            errors.append(f"{k} is {current[k]}, expected {v}")
    return errors


class _Event:

    def __init__(self, raw: Mapping[str, Any]):
        self._raw = raw
        self._caption = self._raw['eventParams'].get('caption', '')
        resource_id = self._raw['eventParams'].get('eventResourceId')
        self._resource_id = UUID(resource_id) if resource_id is not None else None
        self._event_type = self._raw['eventParams']['eventType']
        self._event_subtype = self._raw['eventParams'].get('inputPortId')

    def __repr__(self):
        return (
            f"<{self.__class__.__name__}: caption={self._caption}, "
            f"resource_id={self._resource_id}, event_type={self._event_type},"
            f"event_subtype={self._event_subtype}>")

    def match(
            self,
            resource_id: Optional[UUID] = None,
            event_type: Optional[str] = None,
            caption_pattern: str = '*',
            event_subtype: Optional[str] = None,
            ) -> bool:
        _logger.info(
            "Check if %r matches to resource_id=%s, event_type=%s, caption_pattern=%s",
            self, resource_id, event_type, caption_pattern)
        match = all([
            resource_id == self._resource_id if resource_id is not None else True,
            event_type == self._event_type if event_type is not None else True,
            fnmatch(self._caption, caption_pattern),
            event_subtype == self._event_subtype if event_subtype is not None else True,
            ])
        _logger.info("Is a match: %s", match)
        return match


def list_events(
        api: MediaserverApi,
        camera_id: UUID,
        event_type: str,
        event_subtype: Optional[str] = None,
        ) -> Collection:
    # Not using MediaserverApi.EventQueue here due to possibility that the events will not appear
    # in chronological order, see VMS-29449.
    # TODO: Make a method in MediaserverApi (currently similar method belongs to EventQueue)
    params = {
        'cameraId': str(camera_id),
        'event_type': event_type,
        }
    if event_subtype is not None:
        params['event_subtype'] = event_subtype
    result = []
    raw_events = api.http_get('ec2/getEvents', {'from': 0, **params})
    for raw_event in raw_events:
        result.append(_Event(raw_event))
    return result


def browse_for_event(
        api: MediaserverApi,
        resource_id: UUID,
        caption_pattern: str,
        event_type: str,
        event_subtype: Optional[str] = None,
        timeout_sec: float = 30,
        ) -> bool:
    started_at = time.monotonic()
    while time.monotonic() - started_at < timeout_sec:
        events = list_events(
            api=api,
            camera_id=resource_id,
            event_type=event_type,
            event_subtype=event_subtype,
            )
        for event in events:
            if event.match(resource_id, event_type, caption_pattern):
                return True
        time.sleep(1)
    return False  # No corresponding events were generated


def _set_analyzed_stream(api: MediaserverApi, camera_id: UUID, engine_id: UUID, stream: str):
    _logger.info("Setting analyzedStreamIndex to %s", stream)
    api.set_device_analytics_analyzed_stream(camera_id, engine_id, stream)

    def _analyzed_stream_is_set() -> bool:
        device_settings = api.get_device_analytics_settings(camera_id, engine_id)
        return device_settings.stream == stream

    wait_for_truthy(
        _analyzed_stream_is_set,
        description='Analyzed stream is set',
        timeout_sec=30)


def _log_lines_format_is_ok(log: str) -> Collection[str]:
    errors = []
    lines = log.splitlines()
    for line in lines:
        log_entry_re = re.compile(
            r'(metadataTimestampMs \d{13}, currentTimeMs \d{13}, diffFromPrevMs -?\d+, '
            r'diffFromCurrentTimeMs -?\d+; additionalInfo: Queue size \d+; '
            r'(objects: \d+:|bestShot:( {5}x (0(?:.\d*)?|1), y (0(?:.\d*)?|1), width (0(?:.\d*)?|1), '
            r'height (0(?:.\d*)?|1), trackId {[0-9a-z\-]{36}})?)|'
            r' *x \d\.?[0-9e\-]*, y \d\.?[0-9e\-]*, width (0(?:.\d*)?|1), height (0(?:.\d*)?|1), '
            r'trackId {[0-9a-z\-]{36}}(, typeId .+, attributes {.*})?|'
            r'Finished logging at \d{13} ms \(VMS System time \d{13} ms\))',
            )
        if not log_entry_re.match(line):
            errors.append(line)
    return errors


def _list_live_metadata_stream_errors(log_file):
    old_log = ''
    wait_for_new_logs_s = 8
    errors = []
    for i in range(1, 4):
        time.sleep(wait_for_new_logs_s)
        _logger.info("Read %s", log_file)
        new_log = log_file.read_text()
        if not new_log.startswith(old_log):
            error_text = (
                f"Iteration #{i}: New live analytics log doesn't contain metadata from old log")
            errors.append(error_text)
            _logger.error(error_text)
            continue
        log_diff = new_log[len(old_log):]
        _logger.debug("Iteration #%d: Log diff calculated", i)
        if not len(log_diff) > 0:
            error_text = (
                f"Iteration #{i}: No new metadata was generated within the last "
                f"{wait_for_new_logs_s} sec")
            errors.append(error_text)
            _logger.error(error_text)
            continue
        log_format_errors = _log_lines_format_is_ok(log_diff)
        if log_format_errors:
            error_text = (
                f"Iteration #{i}: Metadata log format is invalid. Faulty lines are: "
                f"{log_format_errors}")
            errors.append(error_text)
            _logger.error(error_text)
            continue
        _logger.info(
            f"Iteration #{i}: Retrieved a valid portion of live metadata")
        old_log = new_log
    return errors


def enable_device_agent(api: MediaserverApi, plugin_name: str, camera_id: UUID) -> None:
    # TODO: Make a NamedTuple DeviceAgent that stores engine_id, camera_id and plugin_name
    engine_collection = api.get_analytics_engine_collection()
    engine = engine_collection.get_by_exact_name(plugin_name)
    api.enable_device_agent(engine, camera_id)


def live_metadata_stream_errors(
        mediaserver: Mediaserver,
        engine_id: UUID,
        camera_id: UUID,
        stream: str,
        ) -> Collection[str]:
    _set_analyzed_stream(mediaserver.api, camera_id, engine_id, stream)
    log_file = _find_live_metadata_stream_log(mediaserver, camera_id, stream)
    return _list_live_metadata_stream_errors(log_file)


def _find_live_metadata_stream_log(mediaserver, camera_id, stream):
    stream_name_in_log_file_name = 'high' if stream == 'primary' else 'low'
    log_file_name = f'live_stream_provider_device_{camera_id}_{stream_name_in_log_file_name}.log'
    [log_file] = mediaserver.list_log_files(mask=log_file_name)
    return log_file


def record_analytics_tracks(
        api: MediaserverApi,
        required_track_count: int = 1,
        timeout_sec: float = 40,
        with_positions: bool = False,
        ):
    _logger.info(
        "Record at least %d analytics tracks within %ds", required_track_count, timeout_sec)
    start_time = time.monotonic()
    start_time_since_epoch_ms = int(time.time() * 1000)
    while True:
        tracks = api.list_analytics_objects_tracks(
            params={'startTime': str(start_time_since_epoch_ms)},  # Return only current tracks
            with_positions=with_positions,
            )
        track_count = len(tracks)
        _logger.debug("Found %d/%d new tracks", track_count, required_track_count)
        if track_count >= required_track_count:
            return tracks
        if time.monotonic() - start_time > timeout_sec:
            raise RuntimeError(f"Not enough analytics tracks recorded after {timeout_sec}s")
        time.sleep(1)


def set_object_streamer_tracks(
        mediaserver: Mediaserver,
        recording_camera_id: UUID,
        skip_service_tracks=False,
        ) -> Sequence[Track]:
    tracks_file = Path(__file__).with_name('object_streamer_tracks.py')
    tracks = load_tracks_from_file(tracks_file)
    if skip_service_tracks:
        tracks = [t for t in tracks if '_service_' not in t.type_id]
    object_stream = make_object_stream_from_tracks(*tracks)
    object_stream_file = mediaserver.os_access.tmp() / 'test_object_stream.json'
    dump_object_stream_to_file(object_stream_file, object_stream)
    engine_collection = mediaserver.api.get_analytics_engine_collection()
    engine = engine_collection.get_stub('Object Streamer')
    enable_device_agent(mediaserver.api, engine.name(), recording_camera_id)
    # Only tracks with best_shots will be written into database
    new_settings = {
        "bestShotGenerationPolicy": "fixedBoundingBoxBestShotGenerationPolicy",
        "frameNumberToGenerateBestShot": 1,
        "streamFile": str(object_stream_file),
        }
    mediaserver.api.set_device_analytics_settings(recording_camera_id, engine.id(), new_settings)
    return tracks


def prepare_one_mediaserver_stand(
        distrib_url: str,
        one_vm_type: str,
        api_version: str,
        exit_stack: ExitStack,
        with_plugins_from_release: Optional[str] = None,
        ):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    stand = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    if isinstance(stand.os_access(), WindowsAccess):
        stand.os_access().disable_netprofm_service()
    mediaserver = stand.mediaserver()
    if with_plugins_from_release is not None:
        os_type = 'linux' if 'ubuntu' in one_vm_type else 'windows'
        alternative_plugin_files = _fetch_alternative_plugin_files(os_type, with_plugins_from_release)
        mediaserver.install_optional_plugins(alternative_plugin_files)
    else:
        _logger.info("Using default analytics plugins")
    mediaserver.enable_optional_plugins(['sample', 'stub'])
    _enable_leak_detector(mediaserver)
    mediaserver.enable_analytics_logs()
    mediaserver.enable_legacy_rules_engine()
    mediaserver.save_analytics_plugin_manifests()
    mediaserver.start()
    mediaserver.api.setup_local_system({'licenseServer': license_server.url()})
    grant_license(mediaserver, license_server)
    return stand


def _fetch_alternative_plugin_files(os_type, with_plugins_from_release):
    path = f'analytics/previous_releases_plugins/{with_plugins_from_release}/{os_type}/plugins_optional/'
    file_names = ['stub_analytics_plugin.zip']
    if os_type == 'linux':
        file_names.append('libsample_analytics_plugin.so')
    else:
        file_names.append('sample_analytics_plugin.dll')
    fetched_plugins = []
    for file_name in file_names:
        file = default_prerequisite_store.fetch(path + file_name)
        # Multiple file plugins are stored as a zip-compressed folder.
        if file.suffix == '.zip':
            shutil.unpack_archive(file, extract_dir=file.parent)
            plugin_dir = file.parent / file.stem
            fetched_plugins.append(plugin_dir)
        else:
            fetched_plugins.append(file)
    return fetched_plugins
