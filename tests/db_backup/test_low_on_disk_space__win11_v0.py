# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.db_backup.test_low_on_disk_space__ import _test_backup_on_start_with_low_disk_space


class test_win11_v0(VMSTest):
    """Test backup on start with low disk space.

    Selection-Tag: gitlab
    See: https://networkoptix.atlassian.net/browse/FT-466
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/47312
    """

    def _run(self, args, exit_stack):
        _test_backup_on_start_with_low_disk_space(args.distrib_url, 'win11', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_win11_v0().main())
