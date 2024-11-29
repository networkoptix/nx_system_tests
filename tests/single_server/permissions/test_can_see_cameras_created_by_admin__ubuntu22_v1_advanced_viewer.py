# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.permissions.test_can_see_cameras_created_by_admin__ import _test_can_see_cameras_created_by_admin


class test_ubuntu22_v1_advanced_viewer(VMSTest):
    """Test can see cameras created by admin.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1765
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1785
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1810
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1818
    """

    def _run(self, args, exit_stack):
        _test_can_see_cameras_created_by_admin(args.distrib_url, 'ubuntu22', 'v1', 'advanced_viewer', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v1_advanced_viewer().main())
