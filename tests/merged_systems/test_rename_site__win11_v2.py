# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.merged_systems.test_rename_site__ import _test_rename_site


class test_win11_v2(VMSTest):
    """Test rename site.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/2079
    """

    def _run(self, args, exit_stack):
        _test_rename_site(args.distrib_url, 'win11', 'v2', exit_stack)


if __name__ == '__main__':
    exit(test_win11_v2().main())
