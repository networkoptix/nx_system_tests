# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import CloudTest
from tests.base_test import VMSTest
from tests.cloud.push_notifications.test_push_notification_to_another_cloud_account__ import _test_reconnect_to_another_cloud_account


class test_ubuntu22_v0_all_users(VMSTest, CloudTest):
    """Test reconnect to another cloud account.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/76487
    """

    def _run(self, args, exit_stack):
        _test_reconnect_to_another_cloud_account(args.cloud_host, args.distrib_url, 'ubuntu22', 'v0', True, exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v0_all_users().main())
