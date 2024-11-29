# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.event_rules.test_long_event__ import _test_long_event


class test_ubuntu22_758ms_v0(VMSTest):
    """Test long event.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/2032
    """

    def _run(self, args, exit_stack):
        _test_long_event(args.distrib_url, 'ubuntu22', 'v0', 758, exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_758ms_v0().main())
