# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.merged_systems.test_change_system_settings__ import _test_change_system_settings


class test_win11_v0(VMSTest):
    """Test change system settings.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/2091
    """

    def _run(self, args, exit_stack):
        _test_change_system_settings(args.distrib_url, 'win11', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_win11_v0().main())
