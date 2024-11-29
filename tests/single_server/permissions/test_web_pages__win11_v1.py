# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.permissions.test_web_pages__ import _test_manage_web_pages


class test_win11_v1(VMSTest):
    """Test manage web pages.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1771
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1788
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1813
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1825
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1868
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1908
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1919
    Selection-Tag: gitlab
    """

    def _run(self, args, exit_stack):
        _test_manage_web_pages(args.distrib_url, 'win11', 'v1', exit_stack)


if __name__ == '__main__':
    exit(test_win11_v1().main())
