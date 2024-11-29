# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.updates.basics.test_update_low_space__ import _test_update_low_space


class test_win11_v0(VMSTest):
    """Test update low space.

    Selection-Tag: gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57922
    """

    def _run(self, args, exit_stack):
        _test_update_low_space(args.distrib_url, 'win11', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_win11_v0().main())
