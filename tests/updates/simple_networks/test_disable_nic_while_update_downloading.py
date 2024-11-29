# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import sys
import time

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import UpdateServer
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from runner.ft_test import run_ft_test
from tests.base_test import VMSTest
from tests.updates.common import platforms


class test_ubuntu22_ubuntu22_v4plus(VMSTest):
    """Test get streams.

    Selection-Tag: gitlab
    Selection-Tag: no_testrail
    TODO: Test steps differ significantly, clarification needed
    See: https://networkoptix.testrail.net/index.php?/cases/view/57969
    """

    def _run(self, args, exit_stack):
        _test_disable_nic_while_update_downloading(args.distrib_url, ('ubuntu22', 'ubuntu22'), 'v4plus', exit_stack)


def _test_disable_nic_while_update_downloading(distrib_url, two_vm_types, api_version, exit_stack):
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
    second_nic_id = two_mediaservers.second.subnet_nic()
    # TODO: Disable update server access for the second mediaserver
    update_server = UpdateServer(update_archive, first.os_access.source_address())
    exit_stack.enter_context(update_server.serving())
    first.api.start_update(update_server.update_info())
    first.api.wait_until_update_downloading()
    second.os_access.networking.disable_interface(second_nic_id)
    # 120 is a sum of 60 plus 60 where the first 60 seconds are needed to be
    # sure that TCP connection pool timeout has expired, second 60 seconds are
    # needed for the high stability of the test.
    first.api.wait_for_neighbors_status('Offline', timeout_sec=120)
    second.os_access.networking.enable_interface(second_nic_id)
    second.api.wait_for_neighbors_status('Online', timeout_sec=60)
    second.os_access.networking.disable_interface(second_nic_id)
    # we are waiting for 70 seconds to be sure that TCP connection pool
    # timeout has expired. This timeout is not configurable yet, but the
    # corresponding task was created (VMS-15962).
    time.sleep(70)  # TODO: Poll the pool state or force its cleanup.
    second.os_access.networking.enable_interface(second_nic_id)
    second.api.wait_for_neighbors_status('Online', timeout_sec=60)
    first.api.wait_until_update_ready_to_install()


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_ubuntu22_ubuntu22_v4plus()]))
