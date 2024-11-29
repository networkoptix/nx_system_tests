# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import CloudTest
from tests.base_test import VMSTest
from tests.health_monitoring.test_metrics_of_users__ import _test_users


class test_win11_v3plus(VMSTest, CloudTest):
    """Test users.

    See: https://networkoptix.atlassian.net/browse/FT-767
    See: https://networkoptix.atlassian.net/browse/FT-768
    See: https://networkoptix.atlassian.net/browse/FT-769
    See: https://networkoptix.atlassian.net/browse/FT-770
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57429
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57430
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57431
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57432
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57433
    """

    def _run(self, args, exit_stack):
        _test_users(args.cloud_host, args.distrib_url, 'win11', 'v3plus', exit_stack)


if __name__ == '__main__':
    exit(test_win11_v3plus().main())
