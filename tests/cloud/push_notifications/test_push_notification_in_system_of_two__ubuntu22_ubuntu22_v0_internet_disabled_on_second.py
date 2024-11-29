# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import CloudTest
from tests.base_test import VMSTest
from tests.cloud.push_notifications.test_push_notification_in_system_of_two__ import _test_system


class test_ubuntu22_ubuntu22_v0_internet_disabled_on_second(VMSTest, CloudTest):
    """Test system.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/67013
    """

    def _run(self, args, exit_stack):
        _test_system(args.cloud_host, args.distrib_url, ('ubuntu22', 'ubuntu22'), False, 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_ubuntu22_v0_internet_disabled_on_second().main())
