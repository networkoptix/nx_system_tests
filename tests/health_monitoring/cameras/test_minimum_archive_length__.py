# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from mediaserver_api import CameraStatus
from mediaserver_scenarios.license_scenarios import grant_license
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from mediaserver_scenarios.software_camera_scenarios import serve_until_status


def _get_actual_camera_metrics(mediaserver_api, camera_id):
    camera_metrics = mediaserver_api.get_metrics('cameras', camera_id)
    return {
        k: camera_metrics[k]
        for k in ('status', 'min_archive_length_sec')
        if k in camera_metrics}


def _test_minimum_archive_length(distrib_url, one_vm_type, api_version, exit_stack):
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
    expected_data = {}
    actual_data = {}
    mediaserver_api.set_camera_archive_days(camera.id, auto=True)
    serve_until_status(mediaserver_api, camera.id, camera_server, CameraStatus.ONLINE)
    expected_data['online', 'auto'] = {'status': CameraStatus.ONLINE}
    actual_data['online', 'auto'] = _get_actual_camera_metrics(mediaserver_api, camera.id)
    mediaserver_api.set_camera_archive_days(camera.id, min_archive_days=3)
    serve_until_status(mediaserver_api, camera.id, camera_server, CameraStatus.ONLINE)
    expected_data['online', 'set'] = {'status': CameraStatus.ONLINE}
    actual_data['online', 'set'] = _get_actual_camera_metrics(mediaserver_api, camera.id)

    mediaserver_api.set_camera_archive_days(camera.id, auto=True)
    mediaserver_api.start_recording(camera.id)
    serve_until_status(mediaserver_api, camera.id, camera_server, CameraStatus.RECORDING)
    expected_data['recording', 'auto'] = {'status': CameraStatus.RECORDING}
    actual_data['recording', 'auto'] = _get_actual_camera_metrics(mediaserver_api, camera.id)
    mediaserver_api.wait_for_camera_status(camera.id, CameraStatus.OFFLINE)
    expected_data['offline_recording', 'auto'] = {'status': CameraStatus.OFFLINE}
    actual_data['offline_recording', 'auto'] = _get_actual_camera_metrics(
        mediaserver_api, camera.id)
    mediaserver_api.set_camera_archive_days(camera.id, min_archive_days=3)
    serve_until_status(mediaserver_api, camera.id, camera_server, CameraStatus.RECORDING)
    expected_data['recording', 'set'] = {
        'status': CameraStatus.RECORDING,
        'min_archive_length_sec': 3 * 24 * 3600}
    actual_data['recording', 'set'] = _get_actual_camera_metrics(mediaserver_api, camera.id)
    mediaserver_api.wait_for_camera_status(camera.id, CameraStatus.OFFLINE)
    expected_data['offline_recording', 'set'] = {
        'status': CameraStatus.OFFLINE,
        'min_archive_length_sec': 3 * 24 * 3600}
    actual_data['offline_recording', 'set'] = _get_actual_camera_metrics(
        mediaserver_api, camera.id)
    mediaserver_api.stop_recording(camera.id)

    mediaserver_api.set_camera_archive_days(camera.id, auto=True)
    expected_data['offline_no_recording', 'auto'] = {'status': CameraStatus.OFFLINE}
    actual_data['offline_no_recording', 'auto'] = _get_actual_camera_metrics(
        mediaserver_api, camera.id)
    mediaserver_api.set_camera_archive_days(camera.id, min_archive_days=3)
    mediaserver_api.wait_for_camera_status(camera.id, CameraStatus.OFFLINE)
    expected_data['offline_no_recording', 'set'] = {'status': CameraStatus.OFFLINE}
    actual_data['offline_no_recording', 'set'] = _get_actual_camera_metrics(
        mediaserver_api, camera.id)

    assert expected_data == actual_data
