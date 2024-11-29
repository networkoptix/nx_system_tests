# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import sys

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import Forbidden
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from runner.ft_test import run_ft_test
from tests.base_test import VMSTest
from tests.external_storages.smb_stand import smb_stand
from tests.infra import assert_raises


class test_ubuntu22_smb_ubuntu22_mediaserver_v1(VMSTest):
    """Test use smb storage as analytic.

    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_use_smb_storage_as_analytic(args.distrib_url, ('ubuntu22', 'ubuntu22'), 'v1', exit_stack)


def _test_use_smb_storage_as_analytic(distrib_url, two_vm_types, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    installer_supplier.distrib().assert_not_older_than(
        'vms_6.0', "Checks are made on NX Client side; See: VMS-47586")
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    stand = smb_stand(two_vm_types, pool, exit_stack)
    api = stand.mediaserver().api
    smb_storage_id = stand.add_storage()
    with assert_raises(Forbidden):
        api.allocate_storage_for_analytics(smb_storage_id)


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_ubuntu22_smb_ubuntu22_mediaserver_v1()]))
