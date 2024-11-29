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
    """Test server became online after update download.

    Selection-Tag: gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57977
    """

    def _run(self, args, exit_stack):
        _test_server_became_online_after_update_download(args.distrib_url, ('ubuntu22', 'ubuntu22'), 'v4plus', exit_stack)


def _test_server_became_online_after_update_download(distrib_url, two_vm_types, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    distrib = installer_supplier.distrib()
    distrib.assert_branch_not_mobile()
    distrib.assert_not_older_than('vms_6.0', "Update tests only supported by VMS 6.0 and newer")
    distrib.assert_updates_support("Update testing is not supported for release builds")
    updates_supplier = installer_supplier.update_supplier()
    vm_types = set(two_vm_types)
    update_archive = updates_supplier.fetch_server_updates([platforms[v] for v in vm_types])
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    two_mediaservers = exit_stack.enter_context(pool.two_mediaservers(two_vm_types))
    first = two_mediaservers.first.installation()
    second = two_mediaservers.second.installation()
    first.disable_update_files_verification()
    second.disable_update_files_verification()
    two_mediaservers.start()
    two_mediaservers.setup_system()
    two_mediaservers.merge()
    first_id, second_id = first.api.get_server_id(), second.api.get_server_id()
    second.stop()
    update_server = UpdateServer(update_archive, first.os_access.source_address(), bytes_per_sec=2 * 1024**2)
    exit_stack.enter_context(update_server.serving())
    first.api.start_update(update_server.update_info())
    first.api.wait_until_update_processed(ignore_server_ids=[second_id])
    # Bandwidth limiting to trace the downloading status
    first_vm = two_mediaservers.first.vm()
    first_vm.vm_control.limit_bandwidth(speed_limit_kbit=1024 * 2**3)
    second.start()
    first.api.wait_for_neighbors_status('Online', timeout_sec=30)
    first.api.wait_until_update_downloading(ignore_server_ids=[first_id])
    first.api.wait_until_update_ready_to_install()


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_ubuntu22_ubuntu22_v4plus()]))
