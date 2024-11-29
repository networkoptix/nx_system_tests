# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.merged_systems.time_synchronization.test_change_primary_server__ import _test_change_primary_server


class test_win2019_win2019_v0(VMSTest):
    """Test change primary server.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1599
    """

    def _run(self, args, exit_stack):
        _test_change_primary_server(args.distrib_url, ('win2019', 'win2019'), 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_win2019_win2019_v0().main())
