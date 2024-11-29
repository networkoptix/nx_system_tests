# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.test_5x_difference__ import _test_5x_difference


class test_ubuntu22_v0(VMSTest):
    """Test 5x difference.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/2842
    """

    def _run(self, args, exit_stack):
        _test_5x_difference(args.distrib_url, 'ubuntu22', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v0().main())
