# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.permissions.event_rules.test_cannot_manage__ import _test_cannot_manage


class test_ubuntu22_v2_viewer(VMSTest):
    """Test cannot manage.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1797
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1807
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1827
    """

    def _run(self, args, exit_stack):
        _test_cannot_manage(args.distrib_url, 'ubuntu22', 'v2', 'viewer', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v2_viewer().main())
