# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import CloudTest
from tests.base_test import VMSTest
from tests.cloud.push_notifications.test_push_notification_events_and_conditions__ import _test_initiate_push_notification


class test_win11_v1(VMSTest, CloudTest):
    """Test initiate push notification.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/67009
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/67011
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/67012
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/67020
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/67021
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/69725
    """

    def _run(self, args, exit_stack):
        _test_initiate_push_notification(args.cloud_host, args.distrib_url, 'win11', 'v1', exit_stack)


if __name__ == '__main__':
    exit(test_win11_v1().main())
