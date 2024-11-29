# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import CloudTest
from tests.base_test import VMSTest
from tests.cloud.test_disconnected_system_removed_for_cloud_users__ import _test_disconnected_system_removed_for_cloud_users


class test_ubuntu22_v0(VMSTest, CloudTest):
    """Test disconnected system removed for cloud users.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/6767
    """

    def _run(self, args, exit_stack):
        _test_disconnected_system_removed_for_cloud_users(args.cloud_host, args.distrib_url, 'ubuntu22', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v0().main())
