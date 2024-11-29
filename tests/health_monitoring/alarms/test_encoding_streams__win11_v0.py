# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.health_monitoring.alarms.test_encoding_streams__ import _test_encoding_streams


class test_win11_v0(VMSTest):
    """Test encoding streams.

    See: https://networkoptix.atlassian.net/browse/FT-879
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57533
    """

    def _run(self, args, exit_stack):
        _test_encoding_streams(args.distrib_url, 'win11', 'v0', 5, exit_stack)


if __name__ == '__main__':
    exit(test_win11_v0().main())
