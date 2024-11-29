# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from doubles.video.multipart_reader import get_frames
from doubles.video.video_compare import match_frames
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.license_scenarios import grant_license
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from mediaserver_scenarios.software_camera_scenarios import record_from_cameras


def _test_5x_difference(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    stand = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    camera_server = MultiPartJpegCameraServer()
    mediaserver = stand.mediaserver()
    mediaserver.start()
    api = stand.api()
    api.setup_local_system({'licenseServer': license_server.url()})
    grant_license(mediaserver, license_server)
    os = mediaserver.os_access
    mediaserver = mediaserver
    cameras = add_cameras(mediaserver, camera_server, indices=range(10))
    camera_ids = [camera.id for camera in cameras]
    [default] = api.list_storages()
    periods_on_default = record_from_cameras(api, cameras, camera_server, 10)
    frames_on_default = camera_server.get_frames([camera.path for camera in cameras])
    # Since 4.1 mediaserver compares available space, not total space.
    # Available = total - reserved.
    # Calculate disk sizes so that available spaces are 4 and 2 times greater.
    default_available = default.space - default.reserved_space
    large_available = default_available * 4
    small_available = default_available * 2
    large_size = int(large_available / 0.9)
    small_size = int(small_available / 0.9)
    large_path = os.mount_fake_disk('L', large_size)
    mediaserver.stop()
    mediaserver.start()
    [default] = api.list_storages(default.path)
    assert default.is_writable
    [large] = api.list_storages(str(large_path))
    default_space_to_compare = default.space - default.reserved_space
    large_space_to_compare = large.space - large.reserved_space
    assert default_space_to_compare / large_space_to_compare < 5
    assert large.is_writable
    small_path = os.mount_fake_disk('S', small_size)
    mediaserver.stop()
    mediaserver.start()
    [default] = api.list_storages(default.path)
    [large] = api.list_storages(str(large_path))
    [small] = api.list_storages(str(small_path))
    default_space_to_compare = default.space - default.reserved_space
    large_space_to_compare = large.space - large.reserved_space
    small_space_to_compare = small.space - small.reserved_space
    assert (large_space_to_compare + small_space_to_compare) / default_space_to_compare > 5
    assert not default.is_writable
    for camera_id, period_on_default, sent_frames in zip(camera_ids, periods_on_default, frames_on_default):
        url = api.mpjpeg_url(camera_id, period_on_default)
        received_frames = get_frames(url)
        skipped, mismatched = match_frames(sent_frames, received_frames)
        assert len(skipped) < 0.1 * len(sent_frames)
        assert not mismatched
    [large] = api.list_storages(str(large_path))
    assert large.is_writable
    [small] = api.list_storages(str(small_path))
    assert small.is_writable
