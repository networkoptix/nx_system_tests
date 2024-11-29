# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from doubles.video.multipart_reader import get_frames
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from mediaserver_scenarios.software_camera_scenarios import record_from_cameras
from tests.cameras_and_storages.zfs_storages.common import _zfs_pool_mountpoint
from tests.cameras_and_storages.zfs_storages.common import configure_running_mediaserver_on_zfs
from tests.cameras_and_storages.zfs_storages.common import disable_non_zfs_storages


def _test_record_from_camera(distrib_url, one_vm_type, mirrored, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    camera_server = MultiPartJpegCameraServer()
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    api = one_mediaserver.api()
    mediaserver = one_mediaserver.mediaserver()
    license_server = LocalLicenseServer()
    configure_running_mediaserver_on_zfs(license_server, one_mediaserver, mirrored)
    disable_non_zfs_storages(api)
    [camera] = add_cameras(mediaserver, camera_server)
    api.enable_secondary_stream(camera.id)
    record_from_cameras(api, [camera], camera_server, 10)
    [camera_physical_id] = [camera.physical_id for camera in api.list_cameras()]
    [zfs_storage] = api.list_storages(within_path=_zfs_pool_mountpoint)
    zfs_archive = mediaserver.archive(zfs_storage.path)
    camera_archive = zfs_archive.camera_archive(camera_physical_id)
    [low_quality_period] = camera_archive.low().list_periods()
    [high_quality_period] = camera_archive.high().list_periods()
    low_quality_url = api.mpjpeg_url(camera.id, low_quality_period)
    high_quality_url = api.mpjpeg_url(camera.id, high_quality_period)
    auth_header = api.make_auth_header()
    assert get_frames(low_quality_url, auth_header=auth_header)
    assert get_frames(high_quality_url, auth_header=auth_header)
