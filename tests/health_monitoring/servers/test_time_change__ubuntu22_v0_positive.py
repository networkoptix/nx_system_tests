# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from datetime import timedelta

from tests.base_test import VMSTest
from tests.health_monitoring.servers.test_time_change__ import _test_time_change


class test_ubuntu22_v0_positive(VMSTest):
    """Test time change.

    See: https://networkoptix.atlassian.net/browse/FT-794
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57600
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57604
    """

    def _run(self, args, exit_stack):
        _test_time_change(args.distrib_url, 'ubuntu22', timedelta(hours=2), 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v0_positive().main())
