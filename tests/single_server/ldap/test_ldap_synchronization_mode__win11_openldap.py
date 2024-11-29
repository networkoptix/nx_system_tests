# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.ldap.test_ldap_synchronization_mode__ import _test_changing_ldap_synchronization_mode


class test_win11_openldap(VMSTest):
    """User synchronization mode can be changed during/after LDAP server connection configuration.

    Selection-Tag: gitlab
    Selection-Tag: 119192
    Selection-Tag: 119193
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/119192
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/119193
    """

    def _run(self, args, exit_stack):
        _test_changing_ldap_synchronization_mode(args.distrib_url, 'win11', 'openldap', exit_stack)


if __name__ == '__main__':
    exit(test_win11_openldap().main())
