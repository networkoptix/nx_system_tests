# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.permissions.test_can_watch_an_archive__ import _test_can_watch_an_archive


class test_win11_v1_admin(VMSTest):
    """Test can watch an archive.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1766
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1786
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1811
    """

    def _run(self, args, exit_stack):
        _test_can_watch_an_archive(args.distrib_url, 'win11', 'v1', 'admin', exit_stack)


if __name__ == '__main__':
    exit(test_win11_v1_admin().main())
