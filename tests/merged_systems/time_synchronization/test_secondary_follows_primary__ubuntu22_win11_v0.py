# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.merged_systems.time_synchronization.test_secondary_follows_primary__ import _test_secondary_follows_primary


class test_ubuntu22_win11_v0(VMSTest):
    """Test secondary follows primary.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1600
    Selection-Tag: gitlab
    """

    def _run(self, args, exit_stack):
        _test_secondary_follows_primary(args.distrib_url, ('ubuntu22', 'win11'), 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_win11_v0().main())
