# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.external_storages.smb_stand import smb_stand
from tests.infra import assert_raises


def _test_disabled_smb_user(distrib_url, two_vm_types, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    stand = smb_stand(two_vm_types, pool, exit_stack)
    api = stand.mediaserver().api
    user = stand.smb_username()
    smb_storage_id = stand.add_storage()
    assert smb_storage_id in [storage.id for storage in api.list_storages()]
    api.remove_storage(smb_storage_id)
    stand.smb_os_access().disable_user(user)
    stand.smb_os_access().close_all_smb_sessions()
    with assert_raises(PermissionError):
        stand.add_storage()
