# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.health_monitoring.alarms.test_camera_count__ import _test_camera_count


class test_ubuntu22_v0(VMSTest):
    """Test camera count.

    See: https://networkoptix.atlassian.net/browse/FT-583
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/63011
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57411
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57760
    """

    def _run(self, args, exit_stack):
        _test_camera_count(args.distrib_url, 'ubuntu22', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v0().main())
