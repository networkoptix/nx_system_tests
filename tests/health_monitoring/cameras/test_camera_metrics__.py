# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time
from functools import partial

from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from mediaserver_api import ApproxAbs
from mediaserver_api import CameraStatus
from mediaserver_scenarios.license_scenarios import grant_license
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from mediaserver_scenarios.software_camera_scenarios import serve_until_status


def _test_camera_metrics(distrib_url, one_vm_type, api_version, exit_stack):
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
    mediaserver_api = one_mediaserver.api()
    mediaserver_api.stop_recording(camera.id)
    actual_data = {}
    mediaserver_api.start_recording(camera.id)
    serve_until_status(mediaserver_api, camera.id, camera_server, CameraStatus.RECORDING)
    get_actual_fps = partial(
        mediaserver_api.get_metrics, 'cameras', camera.id, 'primary', 'actual_fps')
    actual_data['recording'] = get_actual_fps()
    mediaserver_api.wait_for_camera_status(camera.id, CameraStatus.OFFLINE)
    actual_data['offline'] = get_actual_fps()
    mediaserver_api.stop_recording(camera.id)
    serve_until_status(mediaserver_api, camera.id, camera_server, CameraStatus.ONLINE)
    start = time.monotonic()
    while time.monotonic() - start < 10:
        if get_actual_fps() is None:
            break
    actual_data['online'] = get_actual_fps()
    expected_data = {
        'recording': ApproxAbs(30, 1.5),
        'offline': None,
        'online': None}
    assert actual_data == expected_data
