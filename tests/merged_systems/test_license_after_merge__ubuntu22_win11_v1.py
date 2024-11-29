# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.merged_systems.test_license_after_merge__ import _test_license_after_merge


class test_ubuntu22_win11_v1(VMSTest):
    """Test license after merge.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1593
    """

    def _run(self, args, exit_stack):
        _test_license_after_merge(args.distrib_url, ('ubuntu22', 'win11'), 'v1', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_win11_v1().main())
