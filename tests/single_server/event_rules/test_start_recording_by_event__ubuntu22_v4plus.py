# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.event_rules.test_start_recording_by_event__ import _test_start_recording_by_event


class test_ubuntu22_v4plus(VMSTest):
    """Test start recording by event.

    Selection-Tag: gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/29263
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/30435
    """

    def _run(self, args, exit_stack):
        _test_start_recording_by_event(args.distrib_url, 'ubuntu22', 'v4plus', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v4plus().main())
