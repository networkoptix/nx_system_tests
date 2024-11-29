# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.event_rules.test_authentication_with_real_server__ import _test_authentication_with_real_server


class test_ubuntu22_win11_v0(VMSTest):
    """Test authentication with real server.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/30455
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57290
    """

    def _run(self, args, exit_stack):
        _test_authentication_with_real_server(args.distrib_url, ('ubuntu22', 'win11'), 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_win11_v0().main())
