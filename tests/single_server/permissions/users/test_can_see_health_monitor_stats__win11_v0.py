# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.permissions.users.test_can_see_health_monitor_stats__ import _test_can_see_health_monitor_stats


class test_win11_v0(VMSTest):
    """Test can see health monitor stats.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/6219
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/6218
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/6220
    """

    def _run(self, args, exit_stack):
        _test_can_see_health_monitor_stats(args.distrib_url, 'win11', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_win11_v0().main())
