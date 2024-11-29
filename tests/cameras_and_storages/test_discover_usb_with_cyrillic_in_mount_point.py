# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import sys

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from runner.ft_test import run_ft_test
from tests.base_test import VMSTest


class test_ubuntu22_v0(VMSTest):
    """Test discover usb with cyrillic in mount point.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/76412
    """

    def _run(self, args, exit_stack):
        _test_discover_usb_with_cyrillic_in_mount_point(args.distrib_url, 'ubuntu22', 'v0', exit_stack)


def _test_discover_usb_with_cyrillic_in_mount_point(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    mediaserver = one_mediaserver.mediaserver()
    vm = one_mediaserver.hardware()
    os = mediaserver.os_access
    api = one_mediaserver.api()
    mediaserver.update_conf({'allowRemovableStorages': 1})
    vm.add_disk('usb', size_mb=20 * 1024)
    cyrillic_path = 'НОВЫЙ ТОМ'
    path = os.mount_disk(cyrillic_path)
    assert cyrillic_path in str(path)
    mediaserver.start()
    api.setup_local_system()
    storage_type_renamed = api.specific_features().get('partition_type_usb_renamed_to_removable')
    storage_type = 'removable' if storage_type_renamed == 1 else 'usb'
    [usb_storage] = api.list_storages(storage_type=storage_type)
    assert cyrillic_path in usb_storage.path


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_ubuntu22_v0()]))
