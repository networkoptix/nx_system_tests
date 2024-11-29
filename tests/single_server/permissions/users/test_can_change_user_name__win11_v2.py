# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.permissions.users.test_can_change_user_name__ import _test_can_change_user_name


class test_win11_v2(VMSTest):
    """Test can change user name.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/2055
    """

    def _run(self, args, exit_stack):
        _test_can_change_user_name(args.distrib_url, 'win11', 'v2', exit_stack)


if __name__ == '__main__':
    exit(test_win11_v2().main())
