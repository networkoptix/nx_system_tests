# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import CloudTest
from tests.base_test import VMSTest
from tests.cloud.push_notifications.test_push_notification_text__ import _test_push_notification_text


class test_ubuntu22_v0(VMSTest, CloudTest):
    """Test push notification text.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/78400
    """

    def _run(self, args, exit_stack):
        _test_push_notification_text(args.cloud_host, args.distrib_url, 'ubuntu22', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v0().main())
