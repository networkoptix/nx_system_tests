# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.permissions.system_settings.test_can_edit__ import _test_can_edit


class test_win11_v1(VMSTest):
    """Test can edit.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1774
    """

    def _run(self, args, exit_stack):
        _test_can_edit(args.distrib_url, 'win11', 'v1', 'admin', exit_stack)


if __name__ == '__main__':
    exit(test_win11_v1().main())
