# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.merged_systems.failover.test_failover_with_manual_camera__ import _test_failover_for_manually_added_camera


class test_ubuntu22_win11_v0(VMSTest):
    """Test failover for manually added camera.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/6742
    """

    def _run(self, args, exit_stack):
        _test_failover_for_manually_added_camera(args.distrib_url, ('ubuntu22', 'win11'), 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_win11_v0().main())
