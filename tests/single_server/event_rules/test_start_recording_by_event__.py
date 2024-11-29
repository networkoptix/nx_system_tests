# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from mediaserver_api import CameraStatus
from mediaserver_api import EventState
from mediaserver_api import EventType
from mediaserver_api import RuleAction
from mediaserver_scenarios.license_scenarios import grant_license
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from mediaserver_scenarios.software_camera_scenarios import serve_until_status
from tests.waiting import wait_for_equal


def _test_start_recording_by_event(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    camera_server = MultiPartJpegCameraServer()
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    mediaserver = one_mediaserver.mediaserver()
    mediaserver.enable_legacy_rules_engine()
    mediaserver.start()
    mediaserver.api.setup_local_system({'licenseServer': license_server.url()})
    grant_license(mediaserver, license_server)
    [camera] = add_cameras(mediaserver, camera_server)
    record_for = 5
    action = RuleAction.record_for(record_for, [str(camera.id)])
    mediaserver.api.add_event_rule(
        event_type=EventType.USER_DEFINED,
        event_state=EventState.UNDEFINED,
        action=action,
        )
    # We need to make sure that there are no schedule settings
    # and recording will start only by event.
    mediaserver.api.enable_recording(camera.id, clear_schedule=True)
    serve_until_status(mediaserver.api, camera.id, camera_server, CameraStatus.ONLINE)
    mediaserver.api.create_event(caption='Start recording event')
    serve_until_status(
        mediaserver.api,
        camera.id,
        camera_server,
        CameraStatus.RECORDING,
        timeout_sec=120,
        )
    # The recording time should not exceed 5 seconds (cameraRecordingAction.durationMs) too much.
    serve_until_status(
        mediaserver.api,
        camera.id,
        camera_server,
        CameraStatus.ONLINE,
        timeout_sec=10,
        )
    history = [mediaserver.api.get_server_id()]
    wait_for_equal(
        mediaserver.api.get_camera_history,
        history,
        args=[(camera.id)])
    [[period]] = mediaserver.api.list_recorded_periods(
        [(camera.id)], incomplete_ok=False)
    # It's expected that the result duration is in range [4, 7] in seconds.
    # Tolerance for MJPEG is agreed with support team. Tolerance for codecs
    # with GOP (Group Of Pictures) (e.g. H264) is left unchanged.
    # Anyway this test can only use MJPEG codec at the moment, since software
    # camera doesn't support other codecs.
    # TODO: Calculate tolerance for non-MJPEG codecs
    tolerance_low = 0.3 if camera_server.codec == 'mjpeg' else 0.2
    assert record_for - tolerance_low <= period.duration_sec <= record_for + 10
