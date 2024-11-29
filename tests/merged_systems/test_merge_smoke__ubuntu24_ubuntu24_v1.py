# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.merged_systems.test_merge_smoke__ import _test_simplest_merge


class test_ubuntu24_ubuntu24_v1(VMSTest):
    """Test simplest merge.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/69628
    """

    def _run(self, args, exit_stack):
        _test_simplest_merge(args.distrib_url, ('ubuntu24', 'ubuntu24'), 'v1', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu24_ubuntu24_v1().main())
