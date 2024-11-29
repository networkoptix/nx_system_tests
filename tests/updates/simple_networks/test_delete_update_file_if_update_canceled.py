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
from tests.waiting import wait_for_truthy


class test_ubuntu22_v4plus(VMSTest):
    """Test delete update file if update canceled.

    Selection-Tag: gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/58029
    """

    def _run(self, args, exit_stack):
        _test_delete_update_file_if_update_canceled(args.distrib_url, 'ubuntu22', 'v4plus', exit_stack)


def _test_delete_update_file_if_update_canceled(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    distrib = installer_supplier.distrib()
    distrib.assert_branch_not_mobile()
    distrib.assert_not_older_than('vms_6.0', "Update tests only supported by VMS 6.0 and newer")
    distrib.assert_updates_support("Update testing is not supported for release builds")
    updates_supplier = installer_supplier.update_supplier()
    update_archive = updates_supplier.fetch_server_updates([platforms[one_vm_type]])
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().disable_update_files_verification()
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    mediaserver = one_mediaserver.mediaserver()
    update_server = UpdateServer(update_archive, one_mediaserver.os_access().source_address())
    exit_stack.enter_context(update_server.serving())
    update_info = update_server.update_info()
    mediaserver.api.prepare_update(update_server.update_info())
    mediaserver.api.cancel_update()
    [tmp_update_dir] = mediaserver.list_installer_dirs()
    [var_update_dir] = mediaserver.updates_dir.glob('*')
    finished_at = time.monotonic() + 3
    while True:
        files = list(var_update_dir.iterdir())
        if not files:
            break
        if time.monotonic() > finished_at:
            raise RuntimeError(f"Update files were not deleted. Files {files}")
        time.sleep(1)
    mediaserver.api.start_update(update_info)
    wait_for_truthy(
        lambda: tmp_update_dir.exists() and not list(tmp_update_dir.iterdir()),
        description="Extracted files from previous update are removed.",
        timeout_sec=5,
        )


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_ubuntu22_v4plus()]))
