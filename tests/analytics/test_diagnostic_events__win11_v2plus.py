# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.analytics.test_diagnostic_events__ import _test_diagnostic_event_from_stub
from tests.base_test import VMSTest


class test_win11_v2plus(VMSTest):
    """Test diagnostic event from stub.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/34523
    Selection-Tag: gitlab
    """

    def _run(self, args, exit_stack):
        _test_diagnostic_event_from_stub(args.distrib_url, 'win11', 'v2plus', exit_stack)


if __name__ == '__main__':
    exit(test_win11_v2plus().main())
