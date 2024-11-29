# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.zfs_storages.test_is_enabled__ import _test_is_enabled


class test_ubuntu22_v1_stripped(VMSTest):
    """Test is enabled.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/78403
    """

    def _run(self, args, exit_stack):
        _test_is_enabled(args.distrib_url, 'ubuntu22', 'v1', False, exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v1_stripped().main())
