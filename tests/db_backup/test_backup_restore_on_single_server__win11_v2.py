# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.db_backup.test_backup_restore_on_single_server__ import _test_restore_from_scheduled_backup


class test_win11_v2(VMSTest):
    """Test restore from scheduled backup.

    See: https://networkoptix.atlassian.net/browse/FT-224
    See: https://networkoptix.atlassian.net/browse/FT-465
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1677
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1678
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/47307
    """

    def _run(self, args, exit_stack):
        _test_restore_from_scheduled_backup(args.distrib_url, 'win11', 'v2', 10, exit_stack)


if __name__ == '__main__':
    exit(test_win11_v2().main())
