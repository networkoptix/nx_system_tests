# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import CloudTest
from tests.base_test import VMSTest
from tests.updates.basics.test_update_cloud_system_with_same_cloud_host__ import _test_update_cloud_system_with_same_cloud_host


class test_win11_v0(VMSTest, CloudTest):
    """Test update cloud system with same cloud host.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57885
    """

    def _run(self, args, exit_stack):
        _test_update_cloud_system_with_same_cloud_host(args.cloud_host, args.distrib_url, 'win11', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_win11_v0().main())
