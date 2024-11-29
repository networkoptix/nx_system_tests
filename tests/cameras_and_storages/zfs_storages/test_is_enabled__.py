# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.cameras_and_storages.zfs_storages.common import _zfs_pool_mountpoint
from tests.cameras_and_storages.zfs_storages.common import configure_running_mediaserver_on_zfs
from tests.cameras_and_storages.zfs_storages.common import disable_non_zfs_storages


def _test_is_enabled(distrib_url, one_vm_type, api_version, mirrored, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    api = one_mediaserver.api()
    mediaserver = one_mediaserver.mediaserver()
    license_server = LocalLicenseServer()
    configure_running_mediaserver_on_zfs(license_server, one_mediaserver, mirrored)
    disable_non_zfs_storages(api)
    [zfs_storage] = api.list_storages(within_path=_zfs_pool_mountpoint)
    [main_storage] = api.list_storages(str(mediaserver.default_archive_dir))
    assert zfs_storage.is_enabled
    assert zfs_storage.is_writable
    assert not main_storage.is_enabled
