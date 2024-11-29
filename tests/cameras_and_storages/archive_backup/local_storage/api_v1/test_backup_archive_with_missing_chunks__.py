# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import math

from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from mediaserver_api import EventNotOccurred
from mediaserver_api import MediaserverApiV1
from mediaserver_api import RuleActionType
from mediaserver_api import TimePeriod
from mediaserver_scenarios.license_scenarios import grant_license
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from mediaserver_scenarios.software_camera_scenarios import record_from_cameras
from tests.cameras_and_storages.archive_backup.local_storage.common import add_backup_storage


def _collect_failed_sources_events(event_queue):
    events = []
    while True:
        try:
            event = event_queue.wait_for_next()
        except EventNotOccurred:
            return events
        else:
            if event.reason_code == 'backupFailedSourceFileError':
                events.append(event)


def _test_backup_archive_with_missing_chunks(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    camera_server = MultiPartJpegCameraServer()
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    license_server = LocalLicenseServer()
    mediaserver = one_mediaserver.mediaserver()
    mediaserver.update_conf({'mediaFileDuration': 1})
    mediaserver.start(already_started_ok=True)
    api: MediaserverApiV1 = mediaserver.api
    with license_server.serving():
        api.setup_local_system({'licenseServer': license_server.url()}, basic_and_digest_auth_required=False)
        grant_license(mediaserver, license_server)
    vm_control = one_mediaserver.vm().vm_control
    storage = add_backup_storage(mediaserver, vm_control, 'V', 20_000)
    backup_archive = mediaserver.archive(storage.path)

    [camera] = add_cameras(mediaserver, camera_server)
    api.enable_secondary_stream(camera.id)
    record_from_cameras(api, [camera], camera_server, 25)

    main_archive = mediaserver.default_archive()
    camera_archive = main_archive.camera_archive(camera.physical_id)
    [low_gap_period, low_gap_chunk_count] = camera_archive.low().make_gap_in_archive()
    [high_gap_period, high_gap_chunk_count] = camera_archive.high().make_gap_in_archive()

    event_queue = mediaserver.api.event_queue()
    api.set_backup_quality_for_newly_added_cameras(low=True, high=True)
    api.set_backup_all_archive(camera.id)
    event_queue.skip_existing_events()
    api.enable_backup_for_cameras([camera.id])
    api.wait_for_backup_finish()

    failed_sources_events = _collect_failed_sources_events(event_queue)
    expected_event_count = low_gap_chunk_count + high_gap_chunk_count
    actual_show_popup_total_count = 0
    actual_diagnostics_total_count = 0
    for event in failed_sources_events:
        if event.action_type == RuleActionType.SHOW_POPUP:
            actual_show_popup_total_count += event.aggregation_count
        elif event.action_type == RuleActionType.DIAGNOSTIC:
            actual_diagnostics_total_count += event.aggregation_count
    assert actual_show_popup_total_count == expected_event_count
    assert actual_diagnostics_total_count == expected_event_count

    backup_camera_archive = backup_archive.camera_archive(camera.physical_id)
    main_camera_archive = main_archive.camera_archive(camera.physical_id)
    low_backup_periods = backup_camera_archive.low().list_periods()
    high_backup_periods = backup_camera_archive.high().list_periods()
    low_main_periods = main_camera_archive.low().list_periods()
    high_main_periods = main_camera_archive.high().list_periods()

    [first_low_backup_period, second_low_backup_period] = low_backup_periods
    [first_low_main_period, second_low_main_period] = low_main_periods
    assert first_low_backup_period.start == first_low_main_period.start
    second_low_main_period_end = second_low_main_period.end.timestamp()
    second_low_backup_period_end = second_low_backup_period.end.timestamp()
    assert math.isclose(second_low_main_period_end, second_low_backup_period_end, abs_tol=0.1)
    [actual_low_gap_length] = TimePeriod.calculate_gaps(low_backup_periods)
    assert math.isclose(actual_low_gap_length, low_gap_period.duration_sec, rel_tol=0.01)
    low_backup_gap_start = first_low_backup_period.end.timestamp()
    low_main_gap_start_ts = low_gap_period.start.timestamp()
    assert math.isclose(low_backup_gap_start, low_main_gap_start_ts, abs_tol=0.1)
    low_backup_gap_end = second_low_backup_period.start.timestamp()
    low_main_gap_end = low_gap_period.end.timestamp()
    assert math.isclose(low_backup_gap_end, low_main_gap_end, abs_tol=0.1)

    [first_high_backup_period, second_high_backup_period] = high_backup_periods
    [first_high_main_period, second_high_main_period] = high_main_periods
    assert first_high_backup_period.start == first_high_main_period.start
    second_high_main_period_end = second_high_main_period.end.timestamp()
    second_high_backup_period_end = second_high_backup_period.end.timestamp()
    assert math.isclose(second_high_main_period_end, second_high_backup_period_end, abs_tol=0.1)
    [actual_high_gap_length] = TimePeriod.calculate_gaps(high_backup_periods)
    assert math.isclose(actual_high_gap_length, high_gap_period.duration_sec, rel_tol=0.01)
    high_backup_gap_start = first_high_backup_period.end.timestamp()
    high_main_gap_start = high_gap_period.start.timestamp()
    assert math.isclose(high_backup_gap_start, high_main_gap_start, abs_tol=0.1)
    high_backup_gap_end = second_high_backup_period.start.timestamp()
    high_main_gap_end = high_gap_period.end.timestamp()
    assert math.isclose(high_backup_gap_end, high_main_gap_end, abs_tol=0.1)
