# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.db_backup.test_backup_restore_on_merged_system__ import _test_backup_restore


class test_ubuntu22_win11_v1_current(VMSTest):
    """Test backup restore.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1677
    Selection-Tag: gitlab
    """

    def _run(self, args, exit_stack):
        _test_backup_restore(args.distrib_url, ('ubuntu22', 'win11'), 'v1', 'current', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_win11_v1_current().main())
