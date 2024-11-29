# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.ldap.test_change_ldap_user_permissions__ import _test_change_ldap_user_permissions


class test_win11(VMSTest):
    """Test change ldap user permissions.

    Selection-Tag: gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/2571
    """

    def _run(self, args, exit_stack):
        _test_change_ldap_user_permissions(args.distrib_url, 'win11', exit_stack)


if __name__ == '__main__':
    exit(test_win11().main())
