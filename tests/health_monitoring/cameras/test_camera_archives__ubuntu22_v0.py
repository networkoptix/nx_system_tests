# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.health_monitoring.cameras.test_camera_archives__ import _test_camera_archives


class test_ubuntu22_v0(VMSTest):
    """Test camera archives.

    See: https://networkoptix.atlassian.net/browse/FT-503
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/58150
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/58151
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/58152
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/58153
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/58156
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/58178
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/58179
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/58180
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/58181
    """

    def _run(self, args, exit_stack):
        _test_camera_archives(args.distrib_url, 'ubuntu22', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v0().main())
