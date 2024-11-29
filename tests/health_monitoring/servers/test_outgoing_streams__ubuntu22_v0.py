# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.health_monitoring.servers.test_outgoing_streams__ import _test_outgoing_streams


class test_ubuntu22_v0(VMSTest):
    """Test outgoing streams.

    See: https://networkoptix.atlassian.net/browse/FT-789
    See: https://networkoptix.atlassian.net/browse/FT-790
    See: https://networkoptix.atlassian.net/browse/FT-791
    See: https://networkoptix.atlassian.net/browse/FT-792
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57542
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57544
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57543
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57549
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57550
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57551
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57552
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57553
    """

    def _run(self, args, exit_stack):
        _test_outgoing_streams(args.distrib_url, 'ubuntu22', 'v0', 1, exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v0().main())
