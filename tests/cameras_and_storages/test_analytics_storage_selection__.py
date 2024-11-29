# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.storage_preparation import create_smb_share
from os_access import WindowsAccess
from tests.waiting import wait_for_equal

_logger = logging.getLogger(__name__)


def _test_biggest_local_disk_is_chosen(distrib_url, two_vm_types, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    vm_and_mediaserver_vm_network = exit_stack.enter_context(pool.vm_and_mediaserver_vm_network(two_vm_types))
    [[smb_address, _, smb_machine], mediaserver_unit] = vm_and_mediaserver_vm_network
    user = 'UserWithPassword'
    password = 'GoodPassword'
    # Since shares are reused in tests and Windows doesn't delete SMB connections,
    # it's necessary to use different SMB shares for positive and negative tests.
    [share_name, _] = create_smb_share(smb_machine.os_access, user, password, 300 * 1024**3, 'P')
    mediaserver_vm = mediaserver_unit.vm()
    server = mediaserver_unit.installation()
    api = server.api
    os = server.os_access
    if not isinstance(os, WindowsAccess):  # FT doesn't support mounting SMB from Windows yet
        mount_point = os.path('/media/smb/')
        os.mount_smb_share(
            mount_point=mount_point,
            path=f'//{smb_address}/{share_name}',
            username=user,
            password=password,
            )
    mediaserver_vm.vm_control.add_disk('sata', 25 * 1024)
    os.mount_disk('S')
    mediaserver_vm.vm_control.add_disk('sata', 50 * 1024)
    large_disk_mount_point = os.mount_disk('L')
    server.start()
    server.api.setup_local_system()
    [large_storage] = api.list_storages(str(large_disk_mount_point), ignore_offline=True)
    # Large storage is selected as metadata storage
    wait_for_equal(api.get_metadata_storage_id, large_storage.id)
