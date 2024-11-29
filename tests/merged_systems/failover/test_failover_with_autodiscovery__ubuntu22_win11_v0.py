# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.merged_systems.failover.test_failover_with_autodiscovery__ import _test_failover_and_auto_discovery


class test_ubuntu22_win11_v0(VMSTest):
    """Test failover and auto discovery.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/745
    """

    def _run(self, args, exit_stack):
        _test_failover_and_auto_discovery(args.distrib_url, 'v0', ('ubuntu22', 'win11'), 'true', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_win11_v0().main())
