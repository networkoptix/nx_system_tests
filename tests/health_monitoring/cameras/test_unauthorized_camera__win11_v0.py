# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.health_monitoring.cameras.test_unauthorized_camera__ import _test_unauthorized_camera


class test_win11_v0(VMSTest):
    """Test unauthorized camera.

    See: https://networkoptix.atlassian.net/browse/FT-595
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/58165
    """

    def _run(self, args, exit_stack):
        _test_unauthorized_camera(args.distrib_url, 'win11', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_win11_v0().main())
