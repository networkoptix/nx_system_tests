# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.ldap.test_change_user_name__ import _test_change_user_name


class test_win11_openldap(VMSTest):
    """Test change user name.

    Selection-Tag: gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/122121
    """

    def _run(self, args, exit_stack):
        _test_change_user_name(args.distrib_url, 'win11', 'openldap', exit_stack, expected_new_user=True)


if __name__ == '__main__':
    exit(test_win11_openldap().main())
