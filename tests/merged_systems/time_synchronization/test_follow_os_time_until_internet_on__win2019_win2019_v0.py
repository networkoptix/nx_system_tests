# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.merged_systems.time_synchronization.test_follow_os_time_until_internet_on__ import _test_follow_os_time_until_internet_on


class test_win2019_win2019_v0(VMSTest):
    """Test follow os time until internet on.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1601
    """

    def _run(self, args, exit_stack):
        _test_follow_os_time_until_internet_on(args.distrib_url, ('win2019', 'win2019'), 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_win2019_win2019_v0().main())
