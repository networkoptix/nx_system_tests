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
from tests.infra import Failure
from tests.waiting import wait_for_equal


def _test_camera_recording_fixed_duration(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    mediaserver = one_mediaserver.mediaserver()
    mediaserver.start()
    api = one_mediaserver.api()
    api.setup_local_system({'licenseServer': license_server.url()})
    grant_license(mediaserver, license_server)
    camera_server = MultiPartJpegCameraServer()
    [camera] = add_cameras(mediaserver, camera_server)
    api.enable_recording(camera.id, clear_schedule=True)

    # stage 1
    stage1_record_for = 10
    with camera_server.async_serve():
        action = RuleAction.record_for(stage1_record_for, [str(camera.id)])
        stage1_rule_id = api.add_event_rule(
            event_type=EventType.USER_DEFINED,
            event_state=EventState.UNDEFINED,
            action=action,
            )
        api.wait_for_camera_status(camera.id, CameraStatus.ONLINE)
        api.create_event(
            source="device1",
            caption="Door has been opened",
            description="This event may occur if someone opens the door on the first floor",
            )
        api.wait_for_camera_status(camera.id, CameraStatus.RECORDING, stage1_record_for + 5)
        api.wait_for_camera_status(camera.id, CameraStatus.ONLINE, stage1_record_for + 5)
        history = [api.get_server_id()]
        wait_for_equal(
            api.get_camera_history,
            history,
            args=[(camera.id)])
        [[stage1_period]] = api.list_recorded_periods([(camera.id)], incomplete_ok=False)
        assert stage1_record_for - 0.2 <= stage1_period.duration_sec <= stage1_record_for + 10

    # stage 2
    stage2_record_for = 99
    with camera_server.async_serve():
        api.disable_event_rule(stage1_rule_id)
        action = RuleAction.record_for(stage2_record_for, [str(camera.id)])
        api.add_event_rule(
            event_type=EventType.USER_DEFINED,
            event_state=EventState.ACTIVE,
            action=action,
            )
        api.wait_for_camera_status(camera.id, CameraStatus.ONLINE)
        api.create_event(
            source="device1",
            caption="Door has been opened",
            description="This event may occur if someone opens the door on the first floor",
            state=EventState.ACTIVE,
            )
        api.wait_for_camera_status(camera.id, CameraStatus.RECORDING, stage2_record_for + 5)
        api.wait_for_camera_status(camera.id, CameraStatus.ONLINE, stage2_record_for + 5)
        history = [api.get_server_id()]
        wait_for_equal(
            api.get_camera_history,
            history,
            args=[(camera.id)])
        [[*_, stage2_period2]] = api.list_recorded_periods([(camera.id)], incomplete_ok=False)
        assert stage2_record_for - 0.2 <= stage2_period2.duration_sec <= stage2_record_for + 10

    # stage 3
    with camera_server.async_serve():
        api.wait_for_camera_status(camera.id, CameraStatus.ONLINE)
        api.create_event(
            source="device1",
            caption="Door has been opened",
            description="This event may occur if someone opens the door on the first floor",
            state=EventState.INACTIVE,
            )
        try:
            api.wait_for_camera_status(camera.id, CameraStatus.RECORDING, 10)
        except TimeoutError:
            pass
        else:
            raise Failure("The camera started recording at the stage 3")

    # stage 4
    stage4_record_for = 5
    with camera_server.async_serve():
        action = RuleAction.record_for(stage4_record_for, [str(camera.id)])
        api.add_event_rule(
            event_type=EventType.USER_DEFINED,
            event_state=EventState.UNDEFINED,
            action=action,
            )
        api.wait_for_camera_status(camera.id, CameraStatus.ONLINE)
        api.create_event(
            source="device1",
            caption="Door has been opened",
            description="This event may occurs if sbd opens the door on the first floor",
            state=EventState.ACTIVE,
            )
        api.wait_for_camera_status(camera.id, CameraStatus.RECORDING, stage4_record_for + 5)
        api.wait_for_camera_status(camera.id, CameraStatus.ONLINE, stage4_record_for + 5)
        history = [api.get_server_id()]
        wait_for_equal(
            api.get_camera_history,
            history,
            args=[(camera.id)])
        [[*_, stage4_period3]] = api.list_recorded_periods([(camera.id)], incomplete_ok=False)
        assert stage4_record_for - 0.2 <= stage4_period3.duration_sec <= stage4_record_for + 10
