# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.permissions.user_roles.test_manage_user_roles__ import _test_manage_user_roles


class test_ubuntu22_v0(VMSTest):
    """Test manage user roles.

    Selection-Tag: gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1780
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1798
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1808
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1831
    """

    def _run(self, args, exit_stack):
        _test_manage_user_roles(args.distrib_url, 'ubuntu22', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v0().main())
