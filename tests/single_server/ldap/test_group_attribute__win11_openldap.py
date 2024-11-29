# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.ldap.test_group_attribute__ import _test_group_attribute


class test_win11_openldap(VMSTest):
    """Test group attribute.

    Selection-Tag: gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/122137
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/122144
    """

    def _run(self, args, exit_stack):
        _test_group_attribute(args.distrib_url, 'win11', 'openldap', exit_stack)


if __name__ == '__main__':
    exit(test_win11_openldap().main())
