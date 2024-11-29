# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.permissions.test_video_wall__ import _test_videowall_permissions


class test_ubuntu22_v0(VMSTest):
    """Test videowall permissions.

    Selection-Tag: gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1867
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1794
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1803
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1822
    """

    def _run(self, args, exit_stack):
        _test_videowall_permissions(args.distrib_url, 'ubuntu22', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v0().main())
