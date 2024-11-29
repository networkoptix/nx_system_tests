# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from installation import measure_usage_ratio
from installation import usage_ratio_is_close
from mediaserver_scenarios.license_scenarios import grant_license
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from mediaserver_scenarios.software_camera_scenarios import record_from_cameras

_logger = logging.getLogger(__name__)


def _test_storage_usage_proportions(distrib_url, one_vm_type, api_version, exit_stack):
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
    chunk_sec = 1  # Set minimal sample duration to make this test faster.
    camera_count = 10
    recorded_sec = 60
    chunk_count = int(camera_count * recorded_sec / chunk_sec)
    _logger.info(
        "Chunks: %d cameras * %.0f sec / %.0f sec per chunk = %d chunks",
        camera_count, recorded_sec, chunk_sec, chunk_count)
    mediaserver.update_conf({'mediaFileDuration': chunk_sec})
    os = mediaserver.os_access
    api = one_mediaserver.api()
    small_disk_size = 50 * 1024**3
    large_disk_size = small_disk_size * 5
    [default] = api.list_storages()
    small_path = os.mount_fake_disk('S', small_disk_size)
    large_path = os.mount_fake_disk('L', large_disk_size)
    mediaserver.stop()
    mediaserver.start()
    api.disable_storage(default.id)
    volumes = os.volumes()
    small_free_space_before = volumes[small_path].free
    large_free_space_before = volumes[large_path].free
    cameras = add_cameras(mediaserver, camera_server, indices=range(camera_count))
    record_from_cameras(api, cameras, camera_server, recorded_sec)
    [small] = api.list_storages(within_path=str(small_path))
    [large] = api.list_storages(within_path=str(large_path))
    small_archive = mediaserver.archive(small.path)
    large_archive = mediaserver.archive(large.path)
    usage_ratio = measure_usage_ratio(mediaserver, small.path, large.path)
    assert usage_ratio_is_close(
        usage_ratio,
        small_free_space_before - small.reserved_space,
        large_free_space_before - large.reserved_space,
        chunk_count)
    for camera in cameras:
        small_archive.camera_archive(camera.physical_id).high().remove()
        large_archive.camera_archive(camera.physical_id).high().remove()
    other_data_size = small_disk_size
    os.create_file(large_path / 'other_data.bin', file_size_b=other_data_size)
    record_from_cameras(api, cameras, camera_server, recorded_sec)
    [small] = api.list_storages(within_path=str(small_path))
    [large] = api.list_storages(within_path=str(large_path))
    usage_ratio = measure_usage_ratio(mediaserver, small.path, large.path)
    assert usage_ratio_is_close(
        usage_ratio,
        small_free_space_before - small.reserved_space,
        large_free_space_before - large.reserved_space - other_data_size,
        chunk_count)
