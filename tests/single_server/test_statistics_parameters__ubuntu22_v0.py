# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.test_statistics_parameters__ import _test_statistics_parameters


class test_ubuntu22_v0(VMSTest):
    """Test statistics parameters.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/30636
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/30639
    """

    def _run(self, args, exit_stack):
        _test_statistics_parameters(args.distrib_url, 'ubuntu22', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v0().main())
