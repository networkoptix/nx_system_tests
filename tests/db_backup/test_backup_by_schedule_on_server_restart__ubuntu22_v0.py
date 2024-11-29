# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.db_backup.test_backup_by_schedule_on_server_restart__ import _test_backup_by_schedule_on_server_restart


class test_ubuntu22_v0(VMSTest):
    """Test backup by schedule on server restart.

    Selection-Tag: gitlab
    See: https://networkoptix.atlassian.net/browse/FT-461
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/47310
    """

    def _run(self, args, exit_stack):
        _test_backup_by_schedule_on_server_restart(args.distrib_url, 'ubuntu22', 'v0', 20, exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v0().main())
