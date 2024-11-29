# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from mediaserver_scenarios.software_camera_scenarios import record_from_cameras
from tests.cameras_and_storages.zfs_storages.common import _zfs_pool_mountpoint
from tests.cameras_and_storages.zfs_storages.common import configure_running_mediaserver_on_zfs
from tests.cameras_and_storages.zfs_storages.common import disable_non_zfs_storages
from tests.waiting import wait_for_truthy


def _test_storage_is_used_for_analytics(distrib_url, one_vm_type, mirrored, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    camera_server = MultiPartJpegCameraServer()
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    api = one_mediaserver.api()
    mediaserver = one_mediaserver.mediaserver()
    mediaserver.enable_optional_plugins(['sample'])
    license_server = LocalLicenseServer()
    configure_running_mediaserver_on_zfs(license_server, one_mediaserver, mirrored)
    disable_non_zfs_storages(api)
    [camera] = add_cameras(mediaserver, camera_server)
    engine_collection = mediaserver.api.get_analytics_engine_collection()
    sample_engine = engine_collection.get_by_exact_name('Sample')
    api.enable_device_agent(sample_engine, camera.id)
    api.enable_secondary_stream(camera.id)
    [camera_physical_id] = [camera.physical_id for camera in api.list_cameras()]
    [zfs_storage] = api.list_storages(within_path=_zfs_pool_mountpoint)
    zfs_archive = mediaserver.archive(zfs_storage.path)
    api.allocate_storage_for_analytics(zfs_storage.id)
    # Record on camera to write metadata.
    record_from_cameras(api, [camera], camera_server, 10)
    wait_for_truthy(zfs_archive.has_object_detection_db)
    camera_archive = zfs_archive.camera_archive(camera_physical_id)
    wait_for_truthy(camera_archive.has_analytics_data_files)
    wait_for_truthy(camera_archive.has_analytics_index_files)
