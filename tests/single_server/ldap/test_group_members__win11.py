# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.ldap.test_group_members__ import _test_group_members


class test_win11(VMSTest):
    """Test group members.

    Selection-Tag: gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/122168
    """

    def _run(self, args, exit_stack):
        _test_group_members(args.distrib_url, 'win11', exit_stack)


if __name__ == '__main__':
    exit(test_win11().main())
