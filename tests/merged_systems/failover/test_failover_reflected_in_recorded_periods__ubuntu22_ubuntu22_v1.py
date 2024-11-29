# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.merged_systems.failover.test_failover_reflected_in_recorded_periods__ import _test_recorded_period_server_id


class test_ubuntu22_ubuntu22_v1(VMSTest):
    """Test recorded period server id.

    Selection-Tag: no_testrail
    See: https://networkoptix.atlassian.net/browse/FT-1863
    """

    def _run(self, args, exit_stack):
        _test_recorded_period_server_id(args.distrib_url, ('ubuntu22', 'ubuntu22'), 'v1', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_ubuntu22_v1().main())
