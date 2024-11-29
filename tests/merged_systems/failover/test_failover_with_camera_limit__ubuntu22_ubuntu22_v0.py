# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.merged_systems.failover.test_failover_with_camera_limit__ import _test_max_camera_settings


class test_ubuntu22_ubuntu22_v0(VMSTest):
    """Test max camera settings.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/747
    """

    def _run(self, args, exit_stack):
        _test_max_camera_settings(args.distrib_url, ('ubuntu22', 'ubuntu22'), 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_ubuntu22_v0().main())
