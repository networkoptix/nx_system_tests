# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.health_monitoring.alarms.test_log_level__ import _test_log_level


class test_win11_v0_verbose_triggered(VMSTest):
    """Test log level.

    See: https://networkoptix.atlassian.net/browse/FT-519
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/62657
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/62658
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/62659
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/78395
    """

    def _run(self, args, exit_stack):
        _test_log_level(args.distrib_url, 'win11', 'Verbose', True, 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_win11_v0_verbose_triggered().main())
