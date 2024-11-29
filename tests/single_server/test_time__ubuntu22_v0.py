# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.test_time__ import _test_uptime_is_monotonic


class test_ubuntu22_v0(VMSTest):
    """Test uptime is monotonic.

    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_uptime_is_monotonic(args.distrib_url, 'ubuntu22', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v0().main())
