# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import WrongPathError
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.external_storages.smb_stand import smb_stand
from tests.infra import assert_raises


def _test_smb_invalid_url(distrib_url, two_vm_types, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    stand = smb_stand(two_vm_types, pool, exit_stack)
    address = stand.smb_address()
    tree = stand.smb_share_name()
    with assert_raises(PermissionError):
        stand.mediaserver().api.add_storage(f'smb://UserWithPassword@{address}/{tree}', 'smb')
    with assert_raises(PermissionError):
        stand.mediaserver().api.add_storage(f'smb://{address}/{tree}', 'smb')
    with assert_raises(PermissionError):
        stand.mediaserver().api.add_storage(f'smb://UserWithPassword:BadPassword@{address}/{tree}', 'smb')
    with assert_raises(PermissionError):
        stand.mediaserver().api.add_storage(f'smb://BadUser:GoodPassword@{address}/{tree}', 'smb')
    with assert_raises(PermissionError):
        stand.mediaserver().api.add_storage(f'smb://BadUser:BadPassword@{address}/{tree}/WrongPath', 'smb')
    with assert_raises(PermissionError):
        stand.mediaserver().api.add_storage(f'smb://{address}/{tree}/WrongPath', 'smb')
    with assert_raises(WrongPathError):
        stand.mediaserver().api.add_storage(f'smb://UserWithPassword:GoodPassword@{address}/{tree}/WrongPath', 'smb')
