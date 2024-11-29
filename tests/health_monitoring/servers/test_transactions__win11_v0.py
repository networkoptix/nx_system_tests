# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.health_monitoring.servers.test_transactions__ import _test_transactions


class test_win11_v0(VMSTest):
    """Test transactions.

    See: https://networkoptix.atlassian.net/browse/FT-819
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57624
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57625
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57626
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57627
    """

    def _run(self, args, exit_stack):
        _test_transactions(args.distrib_url, 'win11', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_win11_v0().main())
