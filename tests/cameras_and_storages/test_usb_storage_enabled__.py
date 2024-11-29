# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def _test_usb_storage_enabled(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    os = one_mediaserver.mediaserver().os_access
    mediaserver = one_mediaserver.mediaserver()
    api = one_mediaserver.api()
    mediaserver.update_conf({'allowRemovableStorages': 1})
    one_mediaserver.hardware().add_disk('usb', size_mb=20 * 1024)
    usb_disk_mount_point = os.mount_disk('E')
    mediaserver.start()
    api.setup_local_system()
    assert _storage_is_enabled(api, usb_disk_mount_point, ignore_offline=False)
    mediaserver.stop()
    mediaserver.remove_database()  # Clear mediaserver data, including saved storages
    mediaserver.update_conf({'defaultRemovableDriveState': 'read'})
    mediaserver.start()
    # Since ecs_db has been removed, the default credentials should be used.
    # This is to avoid hash comparison problems when enable basic and digest authentications.
    api.reset_credentials()
    api.setup_local_system()
    time.sleep(10)
    assert not _storage_is_enabled(api, usb_disk_mount_point)


def _storage_is_enabled(api, mount_point, ignore_offline=True):
    [storage] = api.list_storages(str(mount_point), ignore_offline=ignore_offline)
    return storage.is_enabled
