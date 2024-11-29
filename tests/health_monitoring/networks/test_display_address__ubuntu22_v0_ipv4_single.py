# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.health_monitoring.networks.test_display_address__ import _test_display_address


class test_ubuntu22_v0_ipv4_single(VMSTest):
    """Test display address.

    See: https://networkoptix.atlassian.net/browse/FT-683
    See: https://networkoptix.atlassian.net/browse/FT-684
    See: https://networkoptix.atlassian.net/browse/FT-689
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/58214
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/58216
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/58215
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/65740
    """

    def _run(self, args, exit_stack):
        _test_display_address(args.distrib_url, 'ubuntu22', 'v0', ['10.10.10.1/24'], exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v0_ipv4_single().main())
