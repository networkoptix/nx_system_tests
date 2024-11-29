# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.health_monitoring.networks.test_enabled_interface__ import _test_enabled_interface


class test_win11_v0(VMSTest):
    """Test enabled interface.

    See: https://networkoptix.atlassian.net/browse/FT-681
    See: https://networkoptix.atlassian.net/browse/FT-690
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/58201
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/65732
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/65748
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/65754
    """

    def _run(self, args, exit_stack):
        _test_enabled_interface(args.distrib_url, 'win11', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_win11_v0().main())
