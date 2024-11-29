# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.test_disk_usage_statistics__ import _test_disk_usage_statistics


class test_win11_v0_two_to_one(VMSTest):
    """Test disk usage statistics.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/2717
    """

    def _run(self, args, exit_stack):
        _test_disk_usage_statistics(args.distrib_url, 'win11', 102400, 51200, [1.4, 2.6], 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_win11_v0_two_to_one().main())
