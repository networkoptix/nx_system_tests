# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.merged_systems.test_merge_two_and_one__ import _test_merge_two_systems


class test_v1(VMSTest):
    """Test merge two systems.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/2081
    """

    def _run(self, args, exit_stack):
        _test_merge_two_systems(args.distrib_url, 'v1', exit_stack)


if __name__ == '__main__':
    exit(test_v1().main())
