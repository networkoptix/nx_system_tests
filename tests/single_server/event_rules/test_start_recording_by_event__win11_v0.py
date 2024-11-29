# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.event_rules.test_start_recording_by_event__ import _test_start_recording_by_event


class test_win11_v0(VMSTest):
    """Test start recording by event.

    Selection-Tag: gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/29263
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/30435
    """

    def _run(self, args, exit_stack):
        _test_start_recording_by_event(args.distrib_url, 'win11', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_win11_v0().main())
