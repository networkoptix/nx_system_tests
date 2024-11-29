# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time
from datetime import datetime
from datetime import timedelta

from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import JPEGSequence
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from installation import measure_usage_ratio
from installation import usage_ratio_is_close
from mediaserver_scenarios.license_scenarios import grant_license
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras


def _test_full_storage_usage_proportions(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    video_source = JPEGSequence(frame_size=(2048, 1024))
    camera_server = MultiPartJpegCameraServer(video_source=video_source)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    mediaserver = one_mediaserver.mediaserver()
    mediaserver.start()
    api = one_mediaserver.api()
    api.setup_local_system({'licenseServer': license_server.url()})
    grant_license(mediaserver, license_server)
    os = mediaserver.os_access
    chunk_sec = 1  # Set minimal sample duration to make this test faster.
    camera_count = 10
    recorded_sec = 60
    chunk_count = int(camera_count * recorded_sec / chunk_sec)
    mediaserver.update_conf({'mediaFileDuration': chunk_sec})
    [default] = api.list_storages()
    disk_size_mb = int(20 * 1024)
    one_mediaserver.hardware().add_disk('sata', disk_size_mb)
    disk_one_path = os.mount_disk('E')
    one_mediaserver.hardware().add_disk('sata', disk_size_mb)
    disk_two_path = os.mount_disk('F')
    mediaserver.stop()
    mediaserver.start()
    [storage_one] = api.list_storages(str(disk_one_path))
    [storage_two] = api.list_storages(str(disk_two_path))
    volumes = os.volumes()
    storage_one_free_before = volumes[disk_one_path].free
    storage_two_free_before = volumes[disk_two_path].free
    reserved_space_size = 10 * 1024**3
    api.reserve_storage_space(storage_one.id, reserved_space_size)
    storage_one_archive = mediaserver.archive(storage_one.path)
    [camera] = add_cameras(mediaserver, camera_server)
    camera_archive = storage_one_archive.camera_archive(camera.physical_id)
    camera_archive.high().add_fake_record(
        start_time=datetime.now() - timedelta(days=1),
        duration_sec=1200,
        chunk_duration_sec=30,
        )
    api.rebuild_main_archive()
    api.reserve_storage_space(storage_two.id, reserved_space_size)
    other_data = os.path(storage_two.path) / 'other_data.bin'
    other_data_size = int(7.5 * 1024**3)
    os.create_file(other_data, file_size_b=other_data_size)
    api.disable_storage(default.id)
    cameras = add_cameras(mediaserver, camera_server, indices=range(camera_count))
    api.start_recording(*[camera.id for camera in cameras], single_request=True)
    camera_server.serve(time_limit_sec=recorded_sec)  # Enough to keep right proportion
    storage_one_archive.camera_archive(camera.physical_id).remove()
    other_data.unlink()
    time.sleep(5)  # Mediaserver needs some time to write archive
    usage_ratio = measure_usage_ratio(mediaserver, storage_one.path, storage_two.path)
    assert usage_ratio_is_close(
        usage_ratio,
        storage_one_free_before - storage_one.reserved_space,
        storage_two_free_before - storage_two.reserved_space - other_data_size,
        chunk_count)
