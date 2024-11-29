# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.ldap.test_sync_users__ import _test_sync_users


class test_ubuntu22_ad(VMSTest):
    """Test sync users.

    Selection-Tag: gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/115077
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/122074
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/119194
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/120405
    """

    def _run(self, args, exit_stack):
        _test_sync_users(args.distrib_url, 'ubuntu22', 'active_directory', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_ad().main())
