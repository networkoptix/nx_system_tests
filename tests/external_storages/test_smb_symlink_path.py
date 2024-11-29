# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import sys

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from runner.ft_test import run_ft_test
from tests.base_test import VMSTest


class test_ubuntu22_smb_ubuntu22_mediaserver_v1(VMSTest):
    """Test symlink path.

    See: https://networkoptix.atlassian.net/browse/FT-2057
    Selection-Tag: no_testrail
    Selection-Tag: gitlab
    """

    def _run(self, args, exit_stack):
        _test_symlink_path(args.distrib_url, ('ubuntu22', 'ubuntu22'), 'v1', exit_stack)


def _test_symlink_path(distrib_url, two_vm_types, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    vm_and_mediaserver_vm_network = exit_stack.enter_context(pool.vm_and_mediaserver_vm_network(two_vm_types))
    [[smb_address, _, smb_machine], mediaserver_unit] = vm_and_mediaserver_vm_network
    mediaserver = mediaserver_unit.installation()
    api = mediaserver.api
    mediaserver.start()
    api.setup_local_system()
    smb_os_access = smb_machine.os_access
    [user, password] = ('UserWithPassword', 'GoodPassword')
    mount_point = smb_os_access.mount_fake_disk('D', 100 * 1024**3)
    path = mount_point / 'Share'
    path.mkdir()
    smb_os_access.create_user(user, password)
    smb_os_access.allow_access(path, user)
    symlink_path = path.parent / (path.name + '_symlink')
    smb_os_access.run(['ln', '-s', path, symlink_path])
    share_name = 'test_share'
    smb_os_access.create_smb_share(share_name, symlink_path, user)

    # Test mount via API
    storage_id = api.add_smb_storage(smb_address, share_name, user, password)
    storage = api.get_storage(storage_id)
    assert storage.is_online

    # Test mount in OS
    api.remove_storage(storage_id)
    mount_point = '/mnt/smb_share'
    mediaserver.os_access.mount_smb_share(
        mount_point, f'//{smb_address}/{share_name}', user, password)
    [_, storage] = api.set_up_new_storage(mount_point)
    assert storage.is_online


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_ubuntu22_smb_ubuntu22_mediaserver_v1()]))
