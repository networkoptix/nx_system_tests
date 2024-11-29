# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.health_monitoring.test_metrics_do_not_count_small_storage__ import _test_storage_count_less_than_min_space


class test_ubuntu22_v0(VMSTest):
    """Test storage count less than min space.

    See: https://networkoptix.atlassian.net/browse/FT-765
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57596
    Selection-Tag: gitlab
    """

    def _run(self, args, exit_stack):
        _test_storage_count_less_than_min_space(args.distrib_url, 'ubuntu22', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v0().main())
