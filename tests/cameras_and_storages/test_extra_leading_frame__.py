# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from doubles.video.multipart_reader import get_frames
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.license_scenarios import grant_license
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from mediaserver_scenarios.software_camera_scenarios import record_from_cameras


def _get_unexpected_leading_frame(received_frames, unique_frames_count):
    for i in range(1, unique_frames_count):
        if received_frames[0] == received_frames[i]:
            return i
    return None


# VMS-23140: Test to check the fix
def _test_extra_leading_frame(distrib_url, one_vm_type, api_version, exit_stack):
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
    [period] = record_from_cameras(api, [camera], camera_server, 10)
    [sent_frames] = camera_server.get_frames([camera.path])
    url = api.mpjpeg_url(camera.id, period)
    auth_header = api.make_auth_header()
    received_frames = get_frames(url, auth_header=auth_header)
    if len(received_frames) > len(sent_frames):
        unexpected_frame = _get_unexpected_leading_frame(
            received_frames, unique_frames_count=camera_server.video_source.fps)
        if unexpected_frame is not None:
            raise RuntimeError(f"The first frame is the same as {unexpected_frame} frame")
        raise RuntimeError(
            f"There are more frames received ({len(received_frames)}) than sent ({len(sent_frames)})")
