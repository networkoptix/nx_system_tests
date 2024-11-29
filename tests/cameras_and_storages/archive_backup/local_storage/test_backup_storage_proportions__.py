# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import math

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
from tests.cameras_and_storages.archive_backup.local_storage.common import add_backup_storage


def _test_backup_storage_proportions(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    camera_server = MultiPartJpegCameraServer()
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    license_server = LocalLicenseServer()
    mediaserver = one_mediaserver.mediaserver()
    mediaserver.update_conf({'mediaFileDuration': 1})
    mediaserver.start(already_started_ok=True)
    api = mediaserver.api
    with license_server.serving():
        api.setup_local_system({'licenseServer': license_server.url()}, basic_and_digest_auth_required=False)
        grant_license(mediaserver, license_server)
    os = mediaserver.os_access

    storage_one = add_backup_storage(mediaserver, one_mediaserver.vm().vm_control, 'P', 20_000)
    storage_two = add_backup_storage(mediaserver, one_mediaserver.vm().vm_control, 'Q', 40_000)
    volumes = os.volumes()
    volume_one_path = os.path(storage_one.path).parent
    volume_two_path = os.path(storage_two.path).parent
    storage_one_free_before = volumes[volume_one_path].free
    storage_two_free_before = volumes[volume_two_path].free

    chunk_sec = 1
    camera_count = 10
    recorded_sec = 60
    chunk_count = int(camera_count * recorded_sec / chunk_sec)
    cameras = add_cameras(mediaserver, camera_server, indices=range(camera_count))
    camera_ids = [camera.id for camera in cameras]
    api.enable_backup_for_cameras(camera_ids)
    record_from_cameras(api, cameras, camera_server, recorded_sec)

    recorded_archive = mediaserver.default_archive().size_bytes()

    api.wait_for_backup_finish()

    storage_one_archive = mediaserver.archive(storage_one.path).size_bytes()
    storage_two_archive = mediaserver.archive(storage_two.path).size_bytes()

    assert math.isclose(storage_one_archive + storage_two_archive, recorded_archive, rel_tol=0.01)

    usage_ratio = measure_usage_ratio(mediaserver, storage_one.path, storage_two.path)
    assert usage_ratio_is_close(
        usage_ratio,
        storage_one_free_before - storage_one.reserved_space,
        storage_two_free_before - storage_two.reserved_space,
        chunk_count)
