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
from tests.waiting import wait_for_equal


def _test_archive_reindex(distrib_url, one_vm_type, mirrored, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    camera_server = MultiPartJpegCameraServer()
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    mediaserver = one_mediaserver.mediaserver()
    mediaserver.update_conf({'mediaFileDuration': 1})
    api = mediaserver.api
    license_server = LocalLicenseServer()
    configure_running_mediaserver_on_zfs(license_server, one_mediaserver, mirrored)
    disable_non_zfs_storages(api)
    [camera] = add_cameras(mediaserver, camera_server)
    api.enable_secondary_stream(camera.id)
    record_from_cameras(api, [camera], camera_server, 10)
    recorded_periods_before_rebuild = mediaserver.api.list_recorded_periods([camera.id])
    [zfs_storage] = mediaserver.api.list_storages(within_path=_zfs_pool_mountpoint)
    mediaserver.stop()
    zfs_nxdb = mediaserver.nxdb(zfs_storage.path)
    zfs_nxdb.remove()
    mediaserver.start()
    wait_for_equal(
        get_actual=api.list_recorded_periods,
        expected=recorded_periods_before_rebuild,
        args=[[camera.id]],
        timeout_sec=5)
