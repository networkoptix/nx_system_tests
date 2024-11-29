# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.test_usb_storage_enabled__ import _test_usb_storage_enabled


class test_win2019_v0_v0(VMSTest):
    """Test usb storage enabled.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/43072
    """

    def _run(self, args, exit_stack):
        _test_usb_storage_enabled(args.distrib_url, 'win2019', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_win2019_v0_v0().main())
