# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.test_reserved_space_on_storage__ import _test_reserved_space


class test_win2019_v0_usb(VMSTest):
    """Test reserved space.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/43069
    """

    def _run(self, args, exit_stack):
        _test_reserved_space(args.distrib_url, 'win2019', 'usb', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_win2019_v0_usb().main())