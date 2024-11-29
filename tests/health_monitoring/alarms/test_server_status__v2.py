# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.health_monitoring.alarms.test_server_status__ import _test_server_status


class test_v2(VMSTest):
    """Test server status.

    See: https://networkoptix.atlassian.net/browse/FT-517
    See: https://networkoptix.atlassian.net/browse/FT-518
    See: https://networkoptix.atlassian.net/browse/FT-1209
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/62619
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/62621
    """

    def _run(self, args, exit_stack):
        _test_server_status(args.distrib_url, ('ubuntu22', 'win11'), 'v2', exit_stack)


if __name__ == '__main__':
    exit(test_v2().main())
