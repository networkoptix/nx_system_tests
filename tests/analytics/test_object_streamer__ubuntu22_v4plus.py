# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.analytics.test_object_streamer__ import _test_recorded_time_periods
from tests.base_test import VMSTest


class test_ubuntu22_v4plus(VMSTest):
    """Test recorded time periods.

    Selection-Tag: gitlab
    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_recorded_time_periods(args.distrib_url, 'ubuntu22', 'v4plus', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v4plus().main())
