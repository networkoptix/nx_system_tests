# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import sys

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import UpdateServer
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from runner.ft_test import run_ft_test
from tests.base_test import VMSTest
from tests.updates.common import platforms


class test_ubuntu22_ubuntu22_v4plus(VMSTest):
    """Test internet disabling while downloading.

    Selection-Tag: gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57940
    """

    def _run(self, args, exit_stack):
        _test_internet_disabling_while_downloading(args.distrib_url, ('ubuntu22', 'ubuntu22'), 'v4plus', exit_stack)


def _test_internet_disabling_while_downloading(distrib_url, two_vm_types, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    distrib = installer_supplier.distrib()
    distrib.assert_branch_not_mobile()
    distrib.assert_not_older_than('vms_6.0', "Update tests only supported by VMS 6.0 and newer")
    distrib.assert_updates_support("Update testing is not supported for release builds")
    updates_supplier = installer_supplier.update_supplier()
    # TODO: Test does not work as described in the TestRail case and needs to be fixed
    vm_types = set(two_vm_types)
    update_archive = updates_supplier.fetch_server_updates([platforms[v] for v in vm_types])
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    two_mediaservers = exit_stack.enter_context(pool.two_mediaservers(two_vm_types))
    two_mediaservers.first.installation().disable_update_files_verification()
    two_mediaservers.second.installation().disable_update_files_verification()
    two_mediaservers.start()
    two_mediaservers.setup_system()
    two_mediaservers.merge()
    mediaserver = two_mediaservers.first.installation()
    update_server = UpdateServer(update_archive, mediaserver.os_access.source_address())
    exit_stack.enter_context(update_server.serving())
    # TODO: Disable update server access
    mediaserver.api.prepare_update(update_server.update_info())


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_ubuntu22_ubuntu22_v4plus()]))
