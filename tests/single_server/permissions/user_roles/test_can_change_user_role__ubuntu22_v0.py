# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.permissions.user_roles.test_can_change_user_role__ import _test_can_change_user_role


class test_ubuntu22_v0(VMSTest):
    """Test can change user role.

    Selection-Tag: gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/2056
    """

    def _run(self, args, exit_stack):
        _test_can_change_user_role(args.distrib_url, 'ubuntu22', 'v0', 'admin', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v0().main())
