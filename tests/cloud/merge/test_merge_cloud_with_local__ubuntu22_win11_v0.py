# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import CloudTest
from tests.base_test import VMSTest
from tests.cloud.merge.test_merge_cloud_with_local__ import _test_merge_cloud_with_local


class test_ubuntu22_win11_v0(VMSTest, CloudTest):
    """Test merge cloud with local.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/6322
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/6323
    """

    def _run(self, args, exit_stack):
        _test_merge_cloud_with_local(args.cloud_host, args.distrib_url, ('ubuntu22', 'win11'), 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_win11_v0().main())
