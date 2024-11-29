# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.merged_systems.test_merge_take_remote_settings__ import _test_merge_take_remote_settings


class test_ubuntu22_win11_v1(VMSTest):
    """Test merge take remote settings.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1562
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1595
    """

    def _run(self, args, exit_stack):
        _test_merge_take_remote_settings(args.distrib_url, ('ubuntu22', 'win11'), 'v1', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_win11_v1().main())
