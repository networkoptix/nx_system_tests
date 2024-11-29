# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.ldap.test_assign_users_to_groups__ import _test


class test_win11_openldap(VMSTest):
    """Test assign LDAP user to Mediaserver's groups.

    Selection-Tag: gitlab
    Selection-Tag: ldap
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/120541
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/120611
    """

    def _run(self, args, exit_stack):
        _test(args.distrib_url, 'win11', 'openldap', exit_stack)


if __name__ == '__main__':
    exit(test_win11_openldap().main())
