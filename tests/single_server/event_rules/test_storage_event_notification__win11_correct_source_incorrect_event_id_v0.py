# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.event_rules.test_storage_event_notification__ import CORRECT_SOURCE
from tests.single_server.event_rules.test_storage_event_notification__ import INCORRECT_EVENT_IDS
from tests.single_server.event_rules.test_storage_event_notification__ import _test_storage_event_notification


class test_win11_correct_source_incorrect_event_id_v0(VMSTest):
    """Test storage event notification.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57301
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57374
    """

    def _run(self, args, exit_stack):
        _test_storage_event_notification(args.distrib_url, 'win11', CORRECT_SOURCE, INCORRECT_EVENT_IDS, False, 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_win11_correct_source_incorrect_event_id_v0().main())
