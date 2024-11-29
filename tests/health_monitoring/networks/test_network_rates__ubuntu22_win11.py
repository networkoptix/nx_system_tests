# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.health_monitoring.networks.test_network_rates__ import _test_network_rates


class test_ubuntu22_win11(VMSTest):
    """Test network rates.

    Selection-Tag: gitlab
    See: https://networkoptix.atlassian.net/browse/FT-691
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/65747
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/65753
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/65746
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/65752
    """

    def _run(self, args, exit_stack):
        _test_network_rates(args.distrib_url, ('ubuntu22', 'win11'), 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_win11().main())
