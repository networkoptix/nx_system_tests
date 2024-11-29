# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.permissions.event_rules.test_cannot_edit_event_rule__ import _test_cannot_edit_event_rule


class test_win11_v2_live_viewer(VMSTest):
    """Test cannot edit event rule.

    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_cannot_edit_event_rule(args.distrib_url, 'win11', 'v2', 'live_viewer', exit_stack)


if __name__ == '__main__':
    exit(test_win11_v2_live_viewer().main())
