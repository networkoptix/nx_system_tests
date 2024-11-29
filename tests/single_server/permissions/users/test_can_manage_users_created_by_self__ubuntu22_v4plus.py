# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.permissions.users.test_can_manage_users_created_by_self__ import _test_can_manage_users_created_by_self


class test_ubuntu22_v4plus(VMSTest):
    """Test can manage users created by self.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1762
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/2052
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/2057
    """

    def _run(self, args, exit_stack):
        _test_can_manage_users_created_by_self(args.distrib_url, 'ubuntu22', 'v4plus', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v4plus().main())
