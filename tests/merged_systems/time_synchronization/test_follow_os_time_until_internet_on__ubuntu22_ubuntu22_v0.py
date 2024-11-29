# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.merged_systems.time_synchronization.test_follow_os_time_until_internet_on__ import _test_follow_os_time_until_internet_on


class test_ubuntu22_ubuntu22_v0(VMSTest):
    """Test follow os time until internet on.

    Selection-Tag: gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1601
    """

    def _run(self, args, exit_stack):
        _test_follow_os_time_until_internet_on(args.distrib_url, ('ubuntu22', 'ubuntu22'), 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_ubuntu22_v0().main())
