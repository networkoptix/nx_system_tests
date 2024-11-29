# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import sys

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import UpdateServer
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from runner.ft_test import run_ft_test
from tests.base_test import VMSTest
from tests.updates.common import platforms
from tests.waiting import wait_for_truthy


class test_ubuntu22_v4plus(VMSTest):
    """Test update must be unpacked again after reboot.

    Selection-Tag: gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57865
    """

    def _run(self, args, exit_stack):
        _test_update_must_be_unpacked_again_after_reboot(args.distrib_url, 'ubuntu22', 'v4plus', exit_stack)


def _test_update_must_be_unpacked_again_after_reboot(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    distrib = installer_supplier.distrib()
    distrib.assert_branch_not_mobile()
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    distrib.assert_not_older_than('vms_6.0', "Update tests only supported by VMS 6.0 and newer")
    distrib.assert_updates_support("Update testing is not supported for release builds")
    updates_supplier = installer_supplier.update_supplier()
    # In this case we need to check that update package will be unpacked again
    # after server reboot. To emulate this case I just stop the mediaserver,
    # delete the unpacked update package from the temp folder and start the
    # server again.
    update_archive = updates_supplier.fetch_server_updates([platforms[one_vm_type]])
    mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type)).mediaserver()
    mediaserver.disable_update_files_verification()
    mediaserver.start()
    mediaserver.api.setup_local_system()
    update_server = UpdateServer(update_archive, mediaserver.os_access.source_address())
    exit_stack.enter_context(update_server.serving())
    mediaserver.api.prepare_update(update_server.update_info())
    [tmp_update_dir] = mediaserver.list_installer_dirs()
    assert list(tmp_update_dir.iterdir())
    mediaserver.stop()
    tmp_update_dir.rmtree()
    assert not mediaserver.list_installer_dirs()
    mediaserver.start()
    # Mediaserver needs some time after start to unpack the update archive again.
    [tmp_update_dir] = wait_for_truthy(mediaserver.list_installer_dirs, timeout_sec=5)
    assert list(tmp_update_dir.iterdir())


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_ubuntu22_v4plus()]))
