# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
import logging
import math
import time
from abc import ABCMeta
from abc import abstractmethod
from typing import Sequence

from doubles.video.ffprobe import FfprobeError
from doubles.video.ffprobe import FfprobeNoStreamsError
from doubles.video.ffprobe import ffprobe_get_audio_codec
from doubles.video.ffprobe import ffprobe_get_video_stream
from mediaserver_api import CameraStatus
from mediaserver_api import EventCondition
from mediaserver_api import EventState
from mediaserver_api import EventType
from mediaserver_api import MediaserverApiConnectionError
from mediaserver_api import MediaserverApiHttpError
from mediaserver_api import PTZ_CAPABILITIES
from mediaserver_api import RuleAction
from mediaserver_api import TimePeriod
from real_camera_tests._check_attributes import EqualTo
from real_camera_tests._check_attributes import ExpectedAttributes
from real_camera_tests.camera_actions import add_camera_manually
from real_camera_tests.camera_actions import ffprobe_progress
from real_camera_tests.camera_actions import remove_logical_id
from real_camera_tests.camera_actions import set_logical_id
from real_camera_tests.camera_actions import wait_for_stream
from real_camera_tests.camera_actions import wait_for_video_settings_change
from real_camera_tests.camera_actions import watch_video_stream
from real_camera_tests.camera_stage import AudioConfig
from real_camera_tests.camera_stage import BaseStage
from real_camera_tests.camera_stage import CameraConfig
from real_camera_tests.camera_stage import GenericLinkConfig
from real_camera_tests.camera_stage import IoInputConfig
from real_camera_tests.camera_stage import IoOutputConfig
from real_camera_tests.camera_stage import NvrChannelConfig
from real_camera_tests.camera_stage import NvrFirstChannelConfig
from real_camera_tests.camera_stage import PtzConfig
from real_camera_tests.camera_stage import RealDeviceConfig
from real_camera_tests.camera_stage import Run
from real_camera_tests.camera_stage import SingleRealCameraConfig
from real_camera_tests.camera_stage import StageExecutor
from real_camera_tests.camera_stage import VideoConfig
from real_camera_tests.checks import DictCompareResult
from real_camera_tests.checks import Failure
from real_camera_tests.checks import Halt
from real_camera_tests.checks import PythonExceptionResult
from real_camera_tests.checks import Skipped
from real_camera_tests.checks import Success
from real_camera_tests.checks import VideoCheckResult
from real_camera_tests.checks import check_stream_video_parameters
from real_camera_tests.checks import expect_values

_logger = logging.getLogger(__name__)


def _discovery(run: Run):
    # Needed for cameras with ID starting from "urn_uuid" due to different physicalIds
    # assigned to them upon automatic and manual discovery.
    _logger.debug("Discovery for %s is started", run.name)
    if not isinstance(run.config, (RealDeviceConfig, NvrFirstChannelConfig)):
        return Skipped(f"It's a {run.config.__class__}")
    if run.config.logical_id is not None:
        run.id = run.config.physical_id.auto
    while not run.data:
        yield Failure("Not discovered")
    # If no credentials in config, don't set any, rely on defaults known to Mediaserver.
    if run.config.has_credentials:
        run.server.api.set_camera_credentials(
            run.uuid, run.config.user, run.config.password)
        yield Failure('Try to set credentials')
    if run.config.resource_params_to_set is not None:
        run.server.api.set_camera_resource_params(run.uuid, run.config.resource_params_to_set)
    while run.data.status != CameraStatus.ONLINE:
        yield Failure(f"Not {CameraStatus.ONLINE}")
    if run.config.logical_id is not None:
        yield from set_logical_id(run.server, run.uuid, run.config.logical_id)
    return Success()


def auto_discovery(run: Run):
    return (yield from _discovery(run))


def check_attributes(run):
    if run.config.attributes is None:
        return Skipped("No attributes provided in config")
    while True:
        if run.data is None:
            yield Failure(f"No data received from server for {run.name} {run.id}")
            continue
        actual_attributes = run.data.attributes  # data property makes an API call.
        errors = run.config.attributes.validate(actual_attributes)
        result_string = (
            f"Expected: {run.config.attributes!r}\n"
            f"Actual: {json.dumps(actual_attributes, indent=4)}")
        if errors:
            result_string += f"\nErrors: {json.dumps(errors, indent=4)}"
            yield Failure(result_string)
        else:
            return Success(result_string)


def attributes_auto(run: Run):
    return (yield from check_attributes(run))


class _VideoStageExecutor(StageExecutor, metaclass=ABCMeta):
    _infix: str

    def __init__(
            self,
            timeout: float,
            stage_name: str,
            profile_name: str,
            profile_config: VideoConfig,
            ):
        name = ' '.join([stage_name, profile_name, self._infix, profile_config.name])
        super().__init__(name, timeout)
        self._stage_name = stage_name
        self._profile_name = profile_name
        self._profile_config = profile_config


class _DefaultLiveVideoStageExecutor(_VideoStageExecutor):
    _infix = 'auto recording_off'

    def _execute(self, run: Run):
        run.server.api.stop_recording(run.uuid)
        video_check_result = yield from check_video_parameters(
            run=run,
            profile_name=self._profile_name,
            configuration=self._profile_config,
            check_metrics=False,
            )
        assert video_check_result.is_success(), "It times out or succeeds"
        # Check first frame waiting time for default stream with disabled recording only
        elapsed_time = yield from _check_metrics(run)
        full_result = {
            **video_check_result.raw_result, 'waited_for_stream_s': {'stream': elapsed_time}}
        return VideoCheckResult(raw_result=full_result, is_success=True)


class _DefaultRecordingVideoExecutor(_VideoStageExecutor):
    _infix = 'auto recording_on'

    def _execute(self, run: Run):
        yield from _enable_recording(run, self._profile_name, self._profile_config)
        return (yield from check_video_parameters(
            run=run,
            profile_name=self._profile_name,
            configuration=self._profile_config,
            check_metrics=not isinstance(run.config, NvrChannelConfig),
            ))


class _CustomRecordingVideoExecutor(_VideoStageExecutor):
    _infix = 'set'

    def _execute(self, run: Run):
        yield from _enable_recording(run, self._profile_name, self._profile_config)
        yield from _apply_config(run, self._profile_name, self._profile_config)
        return (yield from check_video_parameters(
            run=run,
            profile_name=self._profile_name,
            configuration=self._profile_config,
            check_metrics=not isinstance(run.config, NvrChannelConfig),
            ))


def streams(camera_config: CameraConfig, is_after_auto=False, *, timeout):
    stage_name = 'stream_auto' if is_after_auto else 'stream_manual'
    config: VideoConfig
    for config in camera_config.primary_default:
        yield _DefaultLiveVideoStageExecutor(
            timeout,
            stage_name,
            'primary',
            config,
            )
        yield _DefaultRecordingVideoExecutor(
            timeout,
            stage_name,
            'primary',
            config,
            )
    for config in camera_config.primary_custom:
        if is_after_auto != config.after_auto:
            continue
        yield _CustomRecordingVideoExecutor(
            timeout,
            stage_name,
            'primary',
            config,
            )
    for config in camera_config.secondary_default:
        yield _DefaultLiveVideoStageExecutor(
            timeout,
            stage_name,
            'secondary',
            config,
            )
        yield _DefaultRecordingVideoExecutor(
            timeout,
            stage_name,
            'secondary',
            config,
            )
    for config in camera_config.secondary_custom:
        if is_after_auto != config.after_auto:
            continue
        yield _CustomRecordingVideoExecutor(
            timeout,
            stage_name,
            'secondary',
            config,
            )


def stream_auto(camera_config, timeout):
    yield from streams(camera_config, is_after_auto=True, timeout=timeout)


class WrongPortDiscoveryStage(BaseStage):

    def __init__(self, timeout):
        self._timeout = timeout

    def make_executors(
            self, camera_config: CameraConfig,
            ) -> Sequence['StageExecutor']:
        # Generic links are added "as is": there's no preliminary accessibility check
        if isinstance(camera_config, GenericLinkConfig):
            return []
        return [WrongPortDiscoveryStageExecutor(self._timeout)]


class WrongPortDiscoveryStageExecutor(StageExecutor):

    def __init__(self, timeout):
        super().__init__("Wrong port discovery", timeout)

    def _execute(self, run: Run):
        # No scheme is specified in discovery_url for physical devices. urlparse puts ip_address to
        # scheme and port to path, so we are forced to parse a string.
        netloc = run.config.discovery_url
        wrong_port = 70
        host, *_ = netloc.split(':')
        try:
            camera = yield from add_camera_manually(
                run.server.api,
                f"{host}:{wrong_port}",
                channel=run.config.channel if isinstance(run.config, NvrChannelConfig) else None,
                user=run.config.user,
                password=run.config.password,
                )
        except run.server.api.CameraNotFound:
            return Success()
        return Failure(f"Camera {camera} was discovered on port {wrong_port}")


def manual_discovery(run: Run):
    # If no credentials in config, search without any. Mediaserver won't use defaults.
    camera = yield from add_camera_manually(
        run.server.api,
        run.config.discovery_url,
        channel=run.config.channel if isinstance(run.config, NvrChannelConfig) else None,
        user=run.config.user,
        password=run.config.password,
        )
    # Logical is used instead of physical because in some cases physical is inconsistent.
    if run.config.logical_id is not None:
        yield from set_logical_id(run.server, camera.id, run.config.logical_id)
    if run.config.resource_params_to_set is not None:
        run.server.api.set_camera_resource_params(run.uuid, run.config.resource_params_to_set)
    while run.data.status != CameraStatus.ONLINE:
        yield Failure(f'Camera status is still not {CameraStatus.ONLINE}')
    return Success()


def camera_manually_added_in_audit_trail(run: Run):
    while True:
        for record in run.server.api.list_audit_trail_records():
            if record.type == run.server.api.audit_trail_events.CAMERA_INSERT and run.uuid in record.resources:
                return Success()
        yield Failure("CameraInsert Audit trail record not found")


def attributes_manual(run: Run):
    return (yield from check_attributes(run))


def view_live_in_audit_trail(run: Run):
    video_length_sec = 30
    abs_tolerance_sec = 15
    started_at_sec = time.time()
    watched_for_sec = yield from watch_video_stream(
        run.server.api.rct_media_url(run.id), video_length_sec)
    if watched_for_sec < video_length_sec - abs_tolerance_sec:
        return Failure(
            f"ffprobe got {watched_for_sec:.1f}s video, expected {video_length_sec}s")
    while True:
        result = Failure("ViewLive Audit trail record not found")
        for record in run.server.api.list_audit_trail_records():
            if record.type == run.server.api.audit_trail_events.VIEW_LIVE and run.uuid in record.resources:
                if record.range_start_sec < started_at_sec:
                    # It is an old record
                    continue
                duration_sec = record.range_end_sec - record.range_start_sec
                res_str = (
                    f"ViewLive record duration is {duration_sec}s, expected "
                    f"{video_length_sec}s +/-{abs_tolerance_sec}s")
                if math.isclose(video_length_sec, duration_sec, abs_tol=abs_tolerance_sec):
                    return Success(res_str)
                else:
                    result = Failure(res_str)
        yield result


def camera_metrics(run: Run):
    # At least for generic links, the ip_address field contains the hostname.
    expected_values = {
        'type': EqualTo(run.config.type), 'ip_address': EqualTo(run.config.hostname)}
    attributes = run.config.attributes
    if attributes is not None:
        if attributes.model() is not None:
            expected_values['model'] = attributes.model()
        if attributes.firmware() is not None:
            expected_values['firmware'] = attributes.firmware()
        if attributes.vendor() is not None:
            expected_values['vendor'] = attributes.vendor()
    expected_attributes = ExpectedAttributes(expected_values)
    metrics_map = run.server.api.get_metrics('cameras', run.uuid)
    errors = expected_attributes.validate(metrics_map)
    result_string = (
        f"Expected: {expected_attributes!r}\n"
        f"Actual: {json.dumps(metrics_map, indent=4)}")
    if errors:
        result_string += f"\nErrors: {json.dumps(errors, indent=4)}"
        return Failure(result_string)
    return Success(result_string)
    yield  # Force this to be an one-shot generator.  # noqa PyUnreachableCode


def configure_video(run: Run, profile, codec, resolution, fps, bitrate_kbps):
    run.server.api.configure_video(run.id, profile, codec, resolution, fps, bitrate_kbps)

    yield from wait_for_video_settings_change(run.server.api.rct_media_url(run.id, profile), codec, resolution)


def _enable_recording(run, profile_name, configuration, force_secondary_stream_fps=False):
    # TODO: For NVR, primary FPS can be set in camera params. Use it?
    if profile_name == 'primary' or force_secondary_stream_fps:
        recording_fps = 15 if configuration.fps is None else configuration.fps
    else:
        schedule = run.data.schedule_tasks
        # VMS-18130: Preserve primary stream FPS when enabling recording.
        recording_fps = schedule[0]['fps'] if schedule else 15
    # Advanced settings aren't applied for some cameras when no stream is requested (VMS-12939)
    rec_quality = configuration.rec_quality
    run.server.api.start_recording(run.uuid, fps=recording_fps, stream_quality=rec_quality)
    while run.data.status != run.config.recording_status:
        yield Failure(
            "Enable recording: "
            f"not {run.config.recording_status}, still {run.data.status}")


def _disable_recording(run):
    run.server.api.stop_recording(run.uuid)
    while run.data.status != CameraStatus.ONLINE:
        yield Failure(
            "Disable recording: "
            f"not {CameraStatus.ONLINE}, still {run.data.status}")


def _apply_config(run, profile_name, configuration):
    # TODO: For NVR, primary FPS can be set in camera params. Use it?
    if profile_name == 'primary':
        configure_fps = None
    else:
        configure_fps = configuration.fps
    yield from configure_video(
        run,
        profile_name,
        configuration.codec,
        configuration.resolution,
        configure_fps,
        configuration.set_bitrate_kbps,
        )


def _check_metrics(run):
    started_at = time.monotonic()
    while time.monotonic() - started_at < 5:
        yield Halt("Sleep to let mediaserver stop stream from camera")
    # Cached GOP is sent very quickly, but real stream starts much later and stream waiting
    # time is irrelevant when calculating time elapsed before receiving cached GOP frames
    elapsed_time = yield from wait_for_stream(
        run.server.api.rct_media_url(run.id, no_cached_gop=True), timeout_s=60)
    return elapsed_time


def check_video_parameters(
        run: Run,
        profile_name,
        configuration: VideoConfig,
        check_metrics: bool,
        ):
    # Check metrics only if recording is enabled.
    # Metrics for NVRs currently are not available, see VMS-19385.
    while True:
        ffprobe_gen = ffprobe_get_video_stream(
            run.server.api.rct_media_url(run.id, profile_name),
            configuration.frames_to_check)
        try:
            ffprobe_params = yield from ffprobe_progress(ffprobe_gen)
        except FfprobeError as e:
            yield Failure(repr(e))
            continue
        metrics_params = {}
        if check_metrics:
            metrics = run.server.api.get_metrics('cameras', run.uuid)
            metrics_params = metrics.get(profile_name, {})
        result, is_result_ok = check_stream_video_parameters(
            ffprobe_params,
            configuration,
            metrics_params,
            check_metrics,
            isinstance(run.config, GenericLinkConfig),
            )
        if not is_result_ok:
            yield VideoCheckResult(raw_result=result, is_success=False)
            continue
        return VideoCheckResult(raw_result=result, is_success=True)


def stream_manual(camera_config, timeout):
    yield from streams(camera_config, timeout=timeout)


class VideoExportMultiStage(BaseStage):

    def __init__(self, timeout):
        self._timeout = timeout

    def make_executors(
            self, camera_config: CameraConfig,
            ) -> Sequence['StageExecutor']:
        result = []
        for stream_name, export_configs in zip(
                ('primary', 'secondary'),
                (camera_config.primary_export_configs, camera_config.secondary_export_configs)):
            if export_configs is None:
                continue
            result.extend([
                RecordFragmentStageExecutor(
                    stream_name, export_configs.original_codec, self._timeout),
                Mp4ExportStageExecutor(export_configs.original_codec, stream_name, self._timeout),
                ViewArchiveInAuditTrailStageExecutor(self._timeout, stream_name),
                ])
            if export_configs.webm_vp8 is not None:
                result.append(
                    WebmExportStageExecutor(export_configs.webm_vp8, stream_name, self._timeout))
            if export_configs.mpjpeg_mjpeg is not None:
                result.append(
                    MpjpegExportStageExecutor(
                        export_configs.mpjpeg_mjpeg, stream_name, self._timeout))
        return result


class RecordFragmentStageExecutor(StageExecutor):

    def __init__(self, stream_name: str, video_config: VideoConfig, timeout):
        super().__init__(f"Record fragment for export: {stream_name}", timeout)
        self._stream_name = stream_name
        self._config = video_config

    def _record_video_fragment(self, run):
        # Workaround for VMS-27915: 2 streams are often put to the same container during export
        disabled_stream = {'primary': 'secondary', 'secondary': 'primary'}[self._stream_name]
        run.server.api.disable_stream_recording(run.uuid, disabled_stream)
        try:
            started_at = time.monotonic()
            yield from _enable_recording(
                run, self._stream_name, self._config, force_secondary_stream_fps=True)
            while time.monotonic() - started_at < self._config.export_duration_sec:
                yield Failure(f"Wait to record {self._config.export_duration_sec}s of video")
            yield from _disable_recording(run)
        finally:
            run.server.api.enable_stream_recording(run.uuid, disabled_stream)

    @staticmethod
    def _get_recorded_period(api, camera_id, init_periods):
        while True:
            try:
                [[period]] = api.list_recorded_periods(
                    camera_ids=[camera_id], incomplete_ok=False, skip_periods=init_periods)
                _logger.debug("Recorded period %s found", period)
                return period
            except ValueError:
                yield Failure("No new recorded periods found yet")
                continue

    def _make_recorded_period(self, run, duration_abs_tolerance_sec):
        while True:
            init_periods = run.server.api.list_recorded_periods(
                camera_ids=[run.uuid], incomplete_ok=False)
            yield Halt("Wait for a sufficient gap between initial and new time periods")
            yield from self._record_video_fragment(run)
            period = yield from self._get_recorded_period(run.server.api, run.uuid, init_periods)
            period_duration_is_ok = (
                period.duration_sec > self._config.export_duration_sec - duration_abs_tolerance_sec
                )
            if period_duration_is_ok:
                _logger.info("Period %s of expected duration found", period)
                return period
            yield Failure(
                f"{period} duration is faulty; expected: {self._config.export_duration_sec}s")

    def _wait_for_nvr_to_record_video(self):
        # Not using time.monotonic(): need to pass absolute time to Server when creating a bookmark
        started_at_ms = int(time.time() * 1000)
        duration_ms = self._config.export_duration_sec * 1000
        while int(time.time() * 1000) < started_at_ms + duration_ms:
            yield Halt(
                f"Wait to record {self._config.export_duration_sec}s of video with desired params")
        return started_at_ms, duration_ms

    def _execute(self, run: Run):
        api = run.server.api
        duration_abs_tolerance_sec = 5
        if isinstance(run.config, NvrChannelConfig):
            # NVR test is different from plain camera because we have no control over NVR recording
            # status. It isn't possible to switch recording off/on to get a new recorded period.
            # NVR is recording constantly and has 1 period that spans for days. Changing the
            # settings of a camera connected to NVR does not produce a new period. We need to apply
            # new settings, wait for duration_ms from this moment and make a respective bookmark.
            api.activate_nvr_channel_license(run.uuid)
            yield from _apply_config(run, self._stream_name, self._config)
            start_time_ms, duration_ms = yield from self._wait_for_nvr_to_record_video()
            api.add_bookmark(
                camera_id=run.uuid,
                name=self._stream_name,
                start_time_ms=start_time_ms,
                duration_ms=duration_ms,
                )
        else:
            if run.data.status == CameraStatus.RECORDING:
                yield from _disable_recording(run)
            if isinstance(run.config, RealDeviceConfig):
                yield from _apply_config(run, self._stream_name, self._config)
            period = yield from self._make_recorded_period(run, duration_abs_tolerance_sec)
            api.add_bookmark_from_time_period(
                camera_id=run.uuid,
                name=self._stream_name,
                period=period,
                )
        return Success()


class VideoExportStageExecutor(StageExecutor):

    def __init__(
            self, video_config: VideoConfig, stream_name, timeout):
        format_name = self.__class__.__dict__['format_name']
        super().__init__(f"Export {format_name} {stream_name}", timeout)
        self._config = video_config
        self._stream_name = stream_name

    @abstractmethod
    def _make_url(self, api, camera_id, period):
        pass

    def _execute(self, run: Run):
        api = run.server.api
        bookmarks = api.list_bookmarks(run.uuid)
        for bookmark in bookmarks:
            if bookmark.name == self._stream_name:
                break
        else:
            return Skipped(f"No bookmark with name {self._stream_name} was found")
        period = TimePeriod(bookmark.start_time_ms, bookmark.duration_ms)
        url = self._make_url(api, run.uuid, period)
        # Server returns 503 error sometimes, we need to re-run ffprobe in this case.
        # Also, for NVR it takes 5+ minutes for fresh archive to become available, many ffprobe
        # re-runs might be needed before frames start to appear.
        while True:
            ffprobe_gen = ffprobe_get_video_stream(url, frames_to_check=None)
            try:
                ffprobe_result = yield from ffprobe_progress(ffprobe_gen)
            except FfprobeError as e:
                yield Failure(str(e))
                continue
            if ffprobe_result is None:
                yield Failure("Failed to retrieve video stream parameters")
            result, result_is_ok = check_stream_video_parameters(
                stream_params=ffprobe_result,
                config_params=self._config,
                metrics_params={},
                check_metrics=False,
                is_generic_link=isinstance(run.config, GenericLinkConfig),
                check_duration=True,
                )
            if result_is_ok:
                return VideoCheckResult(raw_result=result, is_success=result_is_ok)
            yield VideoCheckResult(raw_result=result, is_success=result_is_ok)


class Mp4ExportStageExecutor(VideoExportStageExecutor):

    format_name = "MP4"

    def _make_url(self, api, camera_id, period):
        return api.mp4_url(camera_id, period, self._stream_name)


class WebmExportStageExecutor(VideoExportStageExecutor):

    format_name = 'WebM'

    def _make_url(self, api, camera_id, period):
        return api.webm_url(camera_id, period, self._stream_name, self._config.resolution)


class MpjpegExportStageExecutor(VideoExportStageExecutor):

    format_name = 'MPJPEG'

    def _make_url(self, api, camera_id, period):
        return api.mpjpeg_url(camera_id, period, self._stream_name, self._config.resolution)


class ViewArchiveInAuditTrailStageExecutor(StageExecutor):

    def __init__(self, timeout, bookmark_name):
        super().__init__(f"View Archive Audit Trail record for bookmark {bookmark_name}", timeout)
        self._bookmark_name = bookmark_name

    def _execute(self, run: Run):
        for bookmark in run.server.api.list_bookmarks(run.uuid):
            if bookmark.name == self._bookmark_name:
                _logger.info("Bookmark %s was found", bookmark)
                break
        else:
            return Failure(f"No bookmark with name {self._bookmark_name!r} was found")
        bookmark_duration_sec = round(bookmark.duration_ms / 1000, 1)
        rel_tolerance = 0.3
        while True:
            for record in run.server.api.list_audit_trail_records():
                if record.type != run.server.api.audit_trail_events.VIEW_ARCHIVE:
                    continue
                if run.uuid not in record.resources:
                    continue
                if not math.isclose(record.range_start_sec * 1000, bookmark.start_time_ms, abs_tol=1000):
                    _logger.info(
                        f"Found ViewArchive record {record} with unexpected start time "
                        f"{record.range_start_sec}s, expected {bookmark.start_time_ms / 1000}s")
                    continue
                record_duration_sec = record.range_end_sec - record.range_start_sec
                result_string = (
                    f"ViewArchive record with duration {record_duration_sec}s found: {record}, "
                    f"expected duration is {bookmark_duration_sec}s "
                    f"+/- {bookmark_duration_sec * rel_tolerance}s")
                if math.isclose(bookmark_duration_sec, record_duration_sec, rel_tol=rel_tolerance):
                    return Success(result_string)
                return Failure(result_string)
            yield Failure("ViewArchive Audit trail record not found")


def fps_is_max_when_no_record(run: Run):
    if not isinstance(run.config, SingleRealCameraConfig):
        return Skipped(f"It's a {run.config.__class__}")
    config: VideoConfig = run.config.primary_default[0]
    yield from _enable_recording(run, 'primary', config.with_half_fps())
    yield from _apply_config(run, 'primary', config.with_half_fps())
    half_fps_result = yield from check_video_parameters(
        run,
        profile_name='primary',
        configuration=config.with_half_fps(),
        check_metrics=False,
        )
    assert half_fps_result.is_success()
    run.server.api.stop_recording(run.uuid)
    return (yield from check_video_parameters(
        run,
        profile_name='primary',
        configuration=config,
        check_metrics=False,
        ))


def stream_urls(run: Run):
    while errors := run.config.stream_urls.check(run.data, run.config.hostname):
        yield Failure(errors)
    return Success()


def audio_parameters(run: Run, audio_config: AudioConfig):
    run.server.api.enable_audio(run.uuid)
    if not audio_config.skip_codec_change:
        run.server.api.configure_audio(run.id, audio_config.set_codec)
    stream_url = run.server.api.rct_media_url(run.id)
    _logger.debug("Wait for codec %s to apply to %s", audio_config.codec, stream_url)
    while True:
        ffprobe_gen = ffprobe_get_audio_codec(stream_url)
        try:
            actual_codec = yield from ffprobe_progress(ffprobe_gen)
        except FfprobeError as e:
            yield Failure(repr(e))
            continue
        if actual_codec == audio_config.codec:
            return Success(f"Codec {audio_config.codec} successfully applied to {stream_url}")
        yield Failure(f"Codec {audio_config.codec} was not applied, actual codec {actual_codec}")


class _AudioStageExecutor(StageExecutor):

    def __init__(self, timeout: float, audio_config):
        super().__init__(audio_config.name, timeout)
        self._audio_config = audio_config

    def _execute(self, run: Run):
        return (yield from audio_parameters(run, self._audio_config))


class _DisableAudioStageExecutor(StageExecutor):

    def __init__(self, timeout: float):
        super().__init__("Disable audio", timeout)

    def _execute(self, run: Run):
        run.server.api.disable_audio(run.uuid)
        stream_url = run.server.api.rct_media_url(run.id)
        while True:
            ffprobe_gen = ffprobe_get_audio_codec(stream_url)
            try:
                codec = yield from ffprobe_progress(ffprobe_gen)
            except FfprobeNoStreamsError:
                return Success("No audio stream found")
            except FfprobeError as e:
                yield Failure(str(e))
            else:
                yield Failure(f"Audio stream with codec {codec} is still present")


def audio_stream(camera_config, timeout):
    audio_configs = camera_config.audio
    if not audio_configs:
        return
    for config in audio_configs:
        yield _AudioStageExecutor(timeout, config)
    # This check has to be performed only for cameras that have audio-related data in config
    yield _DisableAudioStageExecutor(timeout)


def _check_io_settings(pins_io_settings, pins_config, pin_type):
    for pin in pins_config:
        if pin.id not in pins_io_settings.ids:
            return Failure(f"No {pin_type} IO pin with id {pin.id} found in Server settings")
        if pin.name is None:
            continue
        settings_name = pins_io_settings.get_name(pin.id)
        if settings_name == pin.name:
            continue
        return Failure(
            f"{pin_type} IO pin {pin.id} name is {settings_name}, expected {pin.name}")


def io_events(run: Run):
    """Check if the camera has specified input and output ports.

    If some inputs have connected outputs: creates event rule on input;
    creates generic event to trigger output;
    generates generic event and checks if the input event rule is triggered.
    """
    if not isinstance(run.config, RealDeviceConfig):
        return Skipped(f"It's a {run.config.__class__}")
    if not run.config.ins and not run.config.outs:
        return Skipped("Neither ins nor outs are specified in the config")
    ins = run.config.ins
    outs = run.config.outs
    _check_io_settings(run.data.io_settings.inputs, ins, 'Input')
    _check_io_settings(run.data.io_settings.outputs, outs, 'Output')
    connected_ins = [port for port in ins if port.connected_out_id is not None]
    if connected_ins:
        run.server.api.add_event_rule(
            EventType.CAMERA_INPUT, EventState.ACTIVE, RuleAction('diagnosticsAction'),
            event_resource_ids=[str(run.uuid)])
        run.server.api.add_event_rule(
            EventType.USER_DEFINED, EventState.UNDEFINED,
            RuleAction('cameraOutputAction', resource_ids=[str(run.uuid)]),
            event_condition=EventCondition(resource_name=run.id))

        # Retry event generation only if retry_event is True; otherwise, generate event only once.
        run.server.api.create_event(source=run.id)
        yield Halt('Waiting for event to trigger inputs')
        while True:
            for port in connected_ins:
                for _ in range(10):
                    events = run.server.api.list_events(run.uuid, 'cameraInputEvent')
                    if events:
                        errors = expect_values(
                            {'eventParams.inputPortId': port.id}, events[-1], 'event')
                        if errors:
                            yield Failure(errors)
                        else:
                            return Success(f"events: {events}, port: {port}")
                    else:
                        yield Failure('No input events from camera')
    return Success("No ins connected")


class IoMultiStage(BaseStage):

    def __init__(self, io_manager, timeout: float = 30):
        self._io_manager = io_manager
        self._timeout = timeout

    def make_executors(
            self, camera_config: RealDeviceConfig,
            ) -> Sequence['StageExecutor']:
        result = []
        if not isinstance(camera_config, RealDeviceConfig):
            return []
        for input_config in camera_config.new_ins:
            result.append(_IoInputStageExecutor(self._io_manager, input_config, self._timeout))
        for output_config in camera_config.new_outs:
            result.append(_IoOutputStageExecutor(self._io_manager, output_config, self._timeout))
        return result


class _IoInputStageExecutor(StageExecutor):

    def __init__(self, io_manager, input_config: IoInputConfig, timeout: float):
        super().__init__(input_config.name, timeout)
        self._io_manager = io_manager
        self._config = input_config

    def add_input_triggered_rule(self, api, camera_uuid):
        api.add_event_rule(
            event_type=EventType.CAMERA_INPUT,
            event_state=EventState.ACTIVE,
            action=RuleAction('diagnosticsAction'),
            event_resource_ids=[str(camera_uuid)],
            event_condition=EventCondition(params={'inputPortId': self._config.id}),
            )

    def _execute(self, run: Run):
        if self._config.id not in run.data.io_settings.inputs.ids:
            return Failure(f"No Input IO pin with id {self._config.id} found in Server settings")
        self.add_input_triggered_rule(run.server.api, run.uuid)
        self._io_manager.activate_device_input_pin(run.name, self._config.pin_name)
        try:
            remaining_attempts = 10
            while True:
                events = run.server.api.list_events(run.uuid, 'cameraInputEvent')
                remaining_attempts -= 1
                if not events:
                    yield Failure("No input events from input %s" % self._config.pin_name)
                    continue
                expected = {'eventParams.inputPortId': self._config.id}
                actual = events[-1]
                errors = expect_values(expected, actual, 'event')
                if errors:
                    fail_result = DictCompareResult(
                        expected=expected,
                        actual=actual,
                        errors=errors,
                        )
                    if remaining_attempts == 0:
                        return fail_result
                    yield fail_result
                    continue
                _logger.info("Input %s test was successful" % self._config.pin_name)
                return DictCompareResult(
                    expected=expected,
                    actual=actual,
                    )
        finally:
            self._io_manager.deactivate_device_input_pin(run.name, self._config.pin_name)


class _IoOutputStageExecutor(StageExecutor):

    def __init__(self, io_manager, output_config: IoOutputConfig, timeout: float):
        super().__init__(output_config.name, timeout)
        self._io_manager = io_manager
        self._config = output_config

    def _add_output_triggering_rule(self, api, camera_uuid, resource_name):
        api.add_event_rule(
            EventType.USER_DEFINED,
            EventState.UNDEFINED,
            RuleAction(
                'cameraOutputAction',
                resource_ids=[str(camera_uuid)],
                params={'relayOutputId': self._config.id},
                ),
            event_condition=EventCondition(resource_name=resource_name))

    def _execute(self, run: Run):
        if self._config.id not in run.data.io_settings.outputs.ids:
            return Failure(f"No Output IO pin with id {self._config.id} found in Server settings")
        self._add_output_triggering_rule(run.server.api, run.uuid, run.id)
        run.server.api.create_event(source=run.id)
        failure = Failure(f"Output {self._config.pin_name} was not activated")
        for _ in range(10):
            if self._io_manager.device_pin_is_enabled(run.name, self._config.pin_name):
                return Success(f"Output {self._config.pin_name} was activated")
            yield failure
        else:
            return failure


def ptz_positions(run: Run):
    """For each position, check if the camera can be moved to this position.

    If positions have attached presets,
    check if the server imported such preset and can move the camera to it.
    """
    if not isinstance(run.config, RealDeviceConfig):
        return Skipped(f"It's a {run.config.__class__}")
    if run.config.ptz is None:
        return Skipped("No ptz specified in the config")
    ptz: PtzConfig
    ptz = run.config.ptz
    expected_capabilities = set(PTZ_CAPABILITIES) - set(ptz.missing_capabilities)
    while run.data.ptz_capabilities != expected_capabilities:
        yield Failure(
            "Capabilities: "
            f"{run.data.ptz_capabilities!r} != {expected_capabilities!r}")
    for use_preset in False, True:
        for pos in ptz.positions:
            if use_preset:
                if pos.preset_id is None:
                    continue
                name = pos.preset_name if pos.preset_name is not None else pos.preset_id
                expected = {'id=' + pos.preset_id: {'name': name}}
                while True:
                    try:
                        actual = run.server.api.execute_ptz(run.id, 'GetPresets')
                    except (MediaserverApiHttpError, MediaserverApiConnectionError) as e:
                        yield PythonExceptionResult(exception=e)
                    else:
                        errors = expect_values(
                            expected,
                            actual,
                            path='<{}>'.format(pos.preset_id),
                            float_abs_error=ptz.float_abs_error)
                        if not errors:
                            break
                        yield DictCompareResult(actual, expected, errors)
                if pos.point is None:
                    continue
                while True:
                    try:
                        run.server.api.execute_ptz(
                            run.id,
                            'ActivatePreset',
                            speed=ptz.speed,
                            presetId=pos.preset_id,
                            )
                    except (MediaserverApiHttpError, MediaserverApiConnectionError) as e:
                        yield PythonExceptionResult(exception=e)
                    else:
                        break
            else:
                if pos.point is None:
                    continue
                move_command = 'AbsoluteLogicalMove' if ptz.is_logical else 'AbsoluteDeviceMove'
                while True:
                    try:
                        run.server.api.execute_ptz(
                            run.id,
                            move_command,
                            speed=ptz.speed,
                            **pos.point.as_dict(),
                            )
                    except (MediaserverApiHttpError, MediaserverApiConnectionError) as e:
                        yield PythonExceptionResult(exception=e)
                    else:
                        break
            yield Halt('Wait for move to {} by {}'.format(
                pos.point.as_dict(), 'preset' if use_preset else 'point'))
            position_command = 'GetLogicalPosition' if ptz.is_logical else 'GetDevicePosition'
            while True:
                try:
                    run.server.api.execute_ptz(
                        run.id,
                        position_command,
                        speed=ptz.speed,
                        **pos.point.as_dict(),
                        )
                except (MediaserverApiHttpError, MediaserverApiConnectionError) as e:
                    yield PythonExceptionResult(exception=e)
                else:
                    break
    return Success()


# https://networkoptix.testrail.net/index.php?/cases/view/952
# https://networkoptix.testrail.net/index.php?/cases/view/1019
def change_device_name(run: Run):
    new_name = f'{run.name}_NewCameraNameForRct'
    run.server.api.rename_camera(run.uuid, new_name)
    while not run.data.name == new_name:
        yield Failure(f"Device name is {run.data.name}, expected {new_name}")
    return Success()


def change_logical_id(run: Run):
    # https://networkoptix.testrail.net/index.php?/cases/view/42087
    logical_id_offset = 1000
    if run.config.logical_id is None:
        # TODO: Is a logical id in the config really necessary? Run the stage anyway.
        return Skipped("No logical id specified in the config; what logical id to try?")
    current_id = run.config.logical_id
    new_id = current_id + logical_id_offset
    yield from set_logical_id(run.server, run.uuid, new_id)
    old_id_data = run.server.api.get_camera(camera_id=current_id, is_uuid=False)
    if old_id_data is not None:
        return Failure(
            f"Some data retrieved when using old logicalId: {current_id}; new id is {new_id}")
    new_id_data = run.server.api.get_camera(camera_id=new_id, is_uuid=False)
    if new_id_data is None:
        return Failure(f"No data retrieved when using new logicalId: {new_id}")
    yield from remove_logical_id(run.server.api, run.uuid)
    zero_id_data = run.server.api.get_camera(camera_id=0, is_uuid=False, validate_logical_id=False)
    if zero_id_data is not None:
        return Failure("Some data was retrieved for camera with logicalId 0")
    return Success()
