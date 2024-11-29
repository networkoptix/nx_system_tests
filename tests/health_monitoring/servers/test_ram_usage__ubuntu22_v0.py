# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.health_monitoring.servers.test_ram_usage__ import _test_ram_usage


class test_ubuntu22_v0(VMSTest):
    """Test ram usage.

    See: https://networkoptix.atlassian.net/browse/FT-777
    See: https://networkoptix.atlassian.net/browse/FT-778
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57480
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57483
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57488
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57491
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57504
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57505
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57506
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57507
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/63034
    """

    def _run(self, args, exit_stack):
        _test_ram_usage(args.distrib_url, 'ubuntu22', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v0().main())
