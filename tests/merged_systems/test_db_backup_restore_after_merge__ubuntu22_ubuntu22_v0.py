# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.merged_systems.test_db_backup_restore_after_merge__ import _test_servers_backed_up_before_merge


class test_ubuntu22_ubuntu22_v0(VMSTest):
    """Test servers backed up before merge.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1561
    """

    def _run(self, args, exit_stack):
        _test_servers_backed_up_before_merge(args.distrib_url, ('ubuntu22', 'ubuntu22'), 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_ubuntu22_v0().main())
