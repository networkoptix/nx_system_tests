# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.merged_systems.test_merge_smoke__ import _test_simplest_merge


class test_ubuntu22_win11_v2(VMSTest):
    """Test simplest merge.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/69628
    """

    def _run(self, args, exit_stack):
        _test_simplest_merge(args.distrib_url, ('ubuntu22', 'win11'), 'v2', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_win11_v2().main())
