# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.health_monitoring.test_metrics_of_system__ import _test_system_info


class test_v2(VMSTest):
    """Test system info.

    See: https://networkoptix.atlassian.net/browse/FT-485
    See: https://networkoptix.atlassian.net/browse/FT-486
    See: https://networkoptix.atlassian.net/browse/FT-488
    See: https://networkoptix.atlassian.net/browse/FT-489
    See: https://networkoptix.atlassian.net/browse/FT-506
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57397
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57563
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57403
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57427
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57415
    """

    def _run(self, args, exit_stack):
        _test_system_info(args.distrib_url, 'v2', exit_stack)


if __name__ == '__main__':
    exit(test_v2().main())
