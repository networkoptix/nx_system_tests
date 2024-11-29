# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time

from directories import get_run_dir
from distrib import BranchNotSupported
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def _test_usb_10x_space_difference(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    mediaserver = one_mediaserver.mediaserver()
    os = mediaserver.os_access
    api = one_mediaserver.api()
    branch = mediaserver.branch()
    if branch.startswith('mobile_'):
        raise BranchNotSupported(f"Branch {branch} is missing VMS-31470 fix.")
    mediaserver.stop()
    usb_disk_size_mb = 22 * 1024
    large_disk_size_mb = usb_disk_size_mb * 11
    one_mediaserver.hardware().add_disk('usb', size_mb=usb_disk_size_mb)
    usb_disk_path = os.mount_disk('U')
    mediaserver.start()
    time.sleep(2)  # Let storages initialize
    [usb_storage] = api.list_storages(str(usb_disk_path), ignore_offline=True)
    assert usb_storage.is_writable
    mediaserver.stop()
    one_mediaserver.hardware().add_disk('sata', size_mb=large_disk_size_mb)
    os.mount_disk('L')
    mediaserver.start()
    time.sleep(2)
    [usb_storage] = api.list_storages(str(usb_disk_path), ignore_offline=True)
    # We don't check 'tooSmall' flag because there are no such flags
    # for storages that never were enabled.
    assert not usb_storage.is_writable
