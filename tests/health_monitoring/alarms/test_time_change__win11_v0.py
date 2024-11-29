# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.health_monitoring.alarms.test_time_change__ import _test_time_change


class test_win11_v0(VMSTest):
    """Test time change.

    See: https://networkoptix.atlassian.net/browse/FT-795
    See: https://networkoptix.atlassian.net/browse/FT-796
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57608
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57609
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57610
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57611
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57763
    """

    def _run(self, args, exit_stack):
        _test_time_change(args.distrib_url, 'win11', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_win11_v0().main())
