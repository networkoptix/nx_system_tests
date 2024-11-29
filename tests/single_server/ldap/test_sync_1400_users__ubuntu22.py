# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.ldap.test_sync_1400_users__ import _test_sync_1400_users


class test_ubuntu22(VMSTest):
    """Test sync 1400 users.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/26265
    """

    def _run(self, args, exit_stack):
        _test_sync_1400_users(args.distrib_url, 'ubuntu22', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22().main())
