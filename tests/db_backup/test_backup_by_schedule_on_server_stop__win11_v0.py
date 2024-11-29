# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.db_backup.test_backup_by_schedule_on_server_stop__ import _test_backup_by_schedule_on_server_stop


class test_win11_v0(VMSTest):
    """Test backup by schedule on server stop.

    Selection-Tag: gitlab
    See: https://networkoptix.atlassian.net/browse/FT-462
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/47311
    """

    def _run(self, args, exit_stack):
        _test_backup_by_schedule_on_server_stop(args.distrib_url, 'win11', 'v0', 10, exit_stack)


if __name__ == '__main__':
    exit(test_win11_v0().main())
