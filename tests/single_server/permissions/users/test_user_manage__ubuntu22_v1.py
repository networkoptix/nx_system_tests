# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.permissions.users.test_user_manage__ import _test_user_manage


class test_ubuntu22_v1(VMSTest):
    """Test user manage.

    Selection-Tag: gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1760
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1798
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1762
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1763
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1808
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1831
    """

    def _run(self, args, exit_stack):
        _test_user_manage(args.distrib_url, 'ubuntu22', 'v1', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v1().main())
