# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from mediaserver_api import CameraStatus
from mediaserver_api import EventState
from mediaserver_api import EventType
from mediaserver_api import RuleAction
from mediaserver_api import RuleActionType
from mediaserver_scenarios.license_scenarios import grant_license
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from mediaserver_scenarios.software_camera_scenarios import serve_until_status


def _test_camera_disconnected_event(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    camera_server = MultiPartJpegCameraServer()
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    mediaserver = one_mediaserver.mediaserver()
    mediaserver.start()
    mediaserver.api.setup_local_system({'licenseServer': license_server.url()})
    grant_license(mediaserver, license_server)
    [camera] = add_cameras(mediaserver, camera_server)
    events = mediaserver.api.event_queue()
    events.skip_existing_events()
    mediaserver.api.disable_event_rules()
    action = RuleAction(RuleActionType.SHOW_POPUP)
    mediaserver.api.add_event_rule(
        event_type=EventType.CAMERA_DISCONNECT,
        event_state=EventState.UNDEFINED,
        event_resource_ids=[str(camera.id)],
        action=action,
        )
    # There is a specification from @sbystrov for the disconnect event: camera should
    # be in recording state or should be open (a client gets a stream from camera),
    # when stop streaming.
    # The test leaves camera in recording state and wait for event raising.
    with mediaserver.api.camera_recording(camera.id):
        serve_until_status(
            mediaserver.api,
            camera.id,
            camera_server,
            CameraStatus.RECORDING,
            timeout_sec=120,
            )
        disconnect_event = events.wait_for_next(timeout_sec=60)
        assert disconnect_event.action_type == action.type
        assert disconnect_event.resource_id == camera.id
        assert disconnect_event.event_type == EventType.CAMERA_DISCONNECT
