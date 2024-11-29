# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.health_monitoring.servers.test_cpu_usage__ import _test_cpu_usage


class test_ubuntu22_v0(VMSTest):
    """Test cpu usage.

    See: https://networkoptix.atlassian.net/browse/FT-775
    See: https://networkoptix.atlassian.net/browse/FT-776
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57475
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57503
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57470
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57502
    """

    def _run(self, args, exit_stack):
        _test_cpu_usage(args.distrib_url, 'ubuntu22', 'v0', 5, exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v0().main())
