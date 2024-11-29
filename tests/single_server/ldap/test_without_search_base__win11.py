# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.ldap.test_without_search_base__ import _test_without_search_base


class test_win11(VMSTest):
    """Test without search base.

    Selection-Tag: gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/119093
    """

    def _run(self, args, exit_stack):
        _test_without_search_base(args.distrib_url, 'win11', exit_stack)


if __name__ == '__main__':
    exit(test_win11().main())
