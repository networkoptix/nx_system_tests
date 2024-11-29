# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.test_add_switch_and_remove_camera__ import _test_add_switch_and_remove_camera


class test_ubuntu22_ubuntu22_v4plus(VMSTest):
    """Test add switch and remove camera.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/2072
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/2073
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/2105
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/2106
    """

    def _run(self, args, exit_stack):
        _test_add_switch_and_remove_camera(args.distrib_url, ('ubuntu22', 'ubuntu22'), 'v4plus', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_ubuntu22_v4plus().main())
