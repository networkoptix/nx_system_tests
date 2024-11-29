# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.license_scenarios import grant_license
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras


def _test_mpjpeg_camera(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    camera_server = MultiPartJpegCameraServer()
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    mediaserver = one_mediaserver.mediaserver()
    mediaserver.start()
    api = one_mediaserver.api()
    api.setup_local_system({'licenseServer': license_server.url()})
    grant_license(mediaserver, license_server)
    [camera] = add_cameras(mediaserver, camera_server)
    api.start_recording(camera.id)
    assert api.recording_is_enabled(camera.id)
    camera_server.serve(time_limit_sec=20, break_on_silence_sec=10)
    api.list_recorded_periods([camera.id], empty_ok=False)
    api.stop_recording(camera.id)
    api.enable_backup_for_cameras([camera.id])
    assert api.camera_backup_is_enabled(camera.id)
    api.disable_backup_for_cameras([camera.id])
    assert not api.camera_backup_is_enabled(camera.id)
    dummy_server_id = api.add_dummy_mediaserver(1)
    api.set_camera_parent(camera.id, dummy_server_id)
    camera = api.get_camera(camera.id)
    assert camera.parent_id == dummy_server_id
    api.set_camera_preferred_parent(camera.id, dummy_server_id)
    camera = api.get_camera(camera.id)
    assert camera.preferred_server_id == dummy_server_id
    api.enable_secondary_stream(camera.id)
    camera = api.get_camera(camera.id)  # Need to re-create camera after changing secondary URL
    assert camera.primary_url.startswith('http')
    assert camera.secondary_url.startswith('http')
