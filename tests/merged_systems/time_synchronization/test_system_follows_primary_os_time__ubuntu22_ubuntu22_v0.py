# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.merged_systems.time_synchronization.test_system_follows_primary_os_time__ import _test_system_follows_primary_os_time


class test_ubuntu22_ubuntu22_v0(VMSTest):
    """Test system follows primary os time.

    Selection-Tag: gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/15861
    """

    def _run(self, args, exit_stack):
        _test_system_follows_primary_os_time(args.distrib_url, ('ubuntu22', 'ubuntu22'), 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_ubuntu22_v0().main())