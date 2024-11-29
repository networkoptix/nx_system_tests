# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time
from typing import cast

from doubles.licensing.local_license_server import LocalLicenseServer
from mediaserver_api import MediaserverApi
from mediaserver_scenarios.provisioned_mediaservers import OneMediaserverStand
from os_access import PosixAccess

_zfs_pool_name = 'new-zfs-pool'
_zfs_pool_mountpoint = '/' + _zfs_pool_name


def configure_running_mediaserver_on_zfs(
        license_server: LocalLicenseServer,
        one_mediaserver: OneMediaserverStand,
        is_mirrored: bool,
        ):
    vm_control = one_mediaserver.hardware()
    os_access = cast(PosixAccess, one_mediaserver.os_access())
    first_disk_size_mb = 15 * 1024
    second_disk_size_mb = 15 * 1024
    vm_control.add_disk('sata', first_disk_size_mb)
    vm_control.add_disk('sata', second_disk_size_mb)
    os_access.create_zfs_pool(pool_name=_zfs_pool_name, disk_count=2, mirrored=is_mirrored)
    mediaserver = one_mediaserver.mediaserver()
    mediaserver.start()
    api = one_mediaserver.api()
    with license_server.serving():
        api.setup_local_system({'licenseServer': license_server.url()})
        mediaserver.allow_license_server_access(license_server.url())
        brand = mediaserver.api.get_brand()
        key = license_server.generate({'BRAND2': brand, 'QUANTITY2': 100})
        mediaserver.api.activate_license(key)
    _wait_until_storage_becomes_writable(api, _zfs_pool_mountpoint)


def disable_non_zfs_storages(mediaserver_api: MediaserverApi):
    for storage in mediaserver_api.list_storages():
        if storage.path.startswith(_zfs_pool_mountpoint):
            continue
        mediaserver_api.disable_storage(storage.id)


def _wait_until_storage_becomes_writable(api: MediaserverApi, mount_point: str):
    finished_at = time.monotonic() + 10
    while True:
        [zfs_storage] = api.list_storages(within_path=mount_point)
        if zfs_storage.is_writable:
            break
        if time.monotonic() > finished_at:
            raise RuntimeError(f"Storage {mount_point!r} is not writable after 10 seconds")
        time.sleep(1)
