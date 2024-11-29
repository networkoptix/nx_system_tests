# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.health_monitoring.test_metrics_request_time__ import _test_metrics_request_time


class test_ubuntu22_win11_v2(VMSTest):
    """Test metrics request time.

    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_metrics_request_time(args.distrib_url, ('ubuntu22', 'win11'), 'v2', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_win11_v2().main())
