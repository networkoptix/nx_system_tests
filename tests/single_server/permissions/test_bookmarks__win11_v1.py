# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.permissions.test_bookmarks__ import _test_manage_bookmark


class test_win11_v1(VMSTest):
    """Test manage bookmark.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/44
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/45
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/46
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/47
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1767
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1787
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1812
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1817
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1820
    """

    def _run(self, args, exit_stack):
        _test_manage_bookmark(args.distrib_url, 'win11', 'v1', exit_stack)


if __name__ == '__main__':
    exit(test_win11_v1().main())
