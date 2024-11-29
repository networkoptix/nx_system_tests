# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import math

from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import JPEGSequence
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.license_scenarios import grant_license
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras


def _test_keep_data_on_db_restore(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    video_source = JPEGSequence(frame_size=(3840, 2160))
    camera_server = MultiPartJpegCameraServer(video_source=video_source)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    mediaserver = one_mediaserver.mediaserver()
    mediaserver.start()
    api = one_mediaserver.api()
    api.setup_local_system({'licenseServer': license_server.url()})
    grant_license(mediaserver, license_server)
    os = mediaserver.os_access
    [default_storage] = api.list_storages()
    # To make sure additional storages will be writable, this must be true:
    # additional storage available space > default storage available space / 10
    # This must be true even if the default storage is disabled.
    # To make this true, reserve the whole default storage space.
    api.reserve_storage_space(default_storage.id, default_storage.space)
    api.disable_storage(default_storage.id)
    # Use smaller chunk size for better archive spreading between storages.
    mediaserver.update_conf({'mediaFileDuration': 2})
    mediaserver.stop()
    small_path = os.mount_fake_disk(letter='S', size_bytes=50 * 1024**3)
    large_path = os.mount_fake_disk(letter='L', size_bytes=100 * 1024**3)
    mediaserver.start()
    time_to_serve_sec = 300
    mjpeg_rate = 3.8 * 1024**2
    # To make archive rotate set 90% of space needed
    space_for_media = time_to_serve_sec * mjpeg_rate * 0.9
    [small] = api.list_storages(str(small_path))
    space_to_reserve = int(small.free_space - space_for_media * 0.33)
    api.reserve_storage_space(small.id, space_to_reserve)
    [large] = api.list_storages(str(large_path))
    small_archive = mediaserver.archive(small.path)
    large_archive = mediaserver.archive(large.path)
    space_to_reserve = int(large.free_space - space_for_media * 0.67)
    api.reserve_storage_space(large.id, space_to_reserve)
    # Smaller storage became not writable, because it was too small before
    # larger storage reserved space changed. So we have to enable it manually.
    api.enable_storage(small.id)
    [small] = api.list_storages(str(small_path))
    [large] = api.list_storages(str(large_path))
    assert small.is_writable
    assert large.is_writable
    [camera] = add_cameras(mediaserver, camera_server)
    api.start_recording(camera.id)
    camera_server.serve(time_to_serve_sec * 0.9)
    mediaserver.stop()
    small_camera_archive = small_archive.camera_archive(camera.physical_id)
    large_camera_archive = large_archive.camera_archive(camera.physical_id)
    small_archive_size_before = small_camera_archive.size_bytes()
    large_archive_size_before = large_camera_archive.size_bytes()
    assert small_archive_size_before > 0
    assert large_archive_size_before > 0
    small_nxdb = mediaserver.nxdb(small.path)
    large_nxdb = mediaserver.nxdb(large.path)
    small_nxdb.remove()
    large_nxdb.remove()
    mediaserver.start()
    camera_server.serve(time_to_serve_sec * 0.1)
    small_archive_size_after = small_camera_archive.size_bytes()
    large_archive_size_after = large_camera_archive.size_bytes()
    assert math.isclose(small_archive_size_after, small_archive_size_before, rel_tol=0.2)
    assert math.isclose(large_archive_size_after, large_archive_size_before, rel_tol=0.2)
