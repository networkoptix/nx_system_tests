# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.health_monitoring.servers.test_server_threads__ import _test_server_threads


class test_ubuntu22_v0(VMSTest):
    """Test server threads.

    See: https://networkoptix.atlassian.net/browse/FT-784
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57512
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57513
    """

    def _run(self, args, exit_stack):
        _test_server_threads(args.distrib_url, 'ubuntu22', 'v0', 15, exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v0().main())
