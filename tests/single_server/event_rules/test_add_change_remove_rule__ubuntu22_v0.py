# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.event_rules.test_add_change_remove_rule__ import _test_add_change_remove_rule


class test_ubuntu22_v0(VMSTest):
    """Test add change remove rule.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/230
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1245
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1246
    Selection-Tag: gitlab
    """

    def _run(self, args, exit_stack):
        _test_add_change_remove_rule(args.distrib_url, 'ubuntu22', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v0().main())
