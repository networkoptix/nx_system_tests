# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.permissions.event_rules.test_cannot_remove_event_rule_created_by_admin__ import _test_cannot_remove_event_rule_created_by_admin


class test_win11_v2_live_viewer(VMSTest):
    """Test cannot remove event rule created by admin.

    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_cannot_remove_event_rule_created_by_admin(args.distrib_url, 'win11', 'v2', 'live_viewer', exit_stack)


if __name__ == '__main__':
    exit(test_win11_v2_live_viewer().main())
