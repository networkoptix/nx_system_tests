# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import CloudTest
from tests.base_test import VMSTest
from tests.cloud.push_notifications.test_push_notification_max_text_size__ import _test_max_notification_text_size


class test_win11_v0(VMSTest, CloudTest):
    """Test max notification text size.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/78382
    """

    def _run(self, args, exit_stack):
        _test_max_notification_text_size(args.cloud_host, args.distrib_url, 'win11', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_win11_v0().main())
