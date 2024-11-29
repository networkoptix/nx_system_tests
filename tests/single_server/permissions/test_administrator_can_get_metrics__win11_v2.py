# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.permissions.test_administrator_can_get_metrics__ import _test_administrator_can_get_metrics


class test_win11_v2(VMSTest):
    """Test administrator can get metrics.

    See: https://networkoptix.atlassian.net/browse/FT-516
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/58308
    """

    def _run(self, args, exit_stack):
        _test_administrator_can_get_metrics(args.distrib_url, 'win11', 'v2', exit_stack)


if __name__ == '__main__':
    exit(test_win11_v2().main())
