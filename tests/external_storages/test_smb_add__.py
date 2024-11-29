# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.external_storages.smb_stand import smb_stand


def _test_add_storage(distrib_url, two_vm_types, api_version, smb_credentials, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    stand = smb_stand(two_vm_types, pool, exit_stack, smb_credentials)
    stand.add_storage()
