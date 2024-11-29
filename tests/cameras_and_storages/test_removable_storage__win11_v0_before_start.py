# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.test_removable_storage__ import _test_removable_storage


class test_win11_v0_before_start(VMSTest):
    """Test removable storage.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/43070
    Selection-Tag: gitlab
    """

    def _run(self, args, exit_stack):
        _test_removable_storage(args.distrib_url, 'win11', True, 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_win11_v0_before_start().main())
