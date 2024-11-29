# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.merged_systems.test_rename_site__ import _test_rename_site


class test_ubuntu22_v4plus(VMSTest):
    """Test rename site.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/2079
    """

    def _run(self, args, exit_stack):
        _test_rename_site(args.distrib_url, 'ubuntu22', 'v4plus', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v4plus().main())
