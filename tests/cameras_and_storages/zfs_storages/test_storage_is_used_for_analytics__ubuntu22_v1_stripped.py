# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.zfs_storages.test_storage_is_used_for_analytics__ import _test_storage_is_used_for_analytics


class test_ubuntu22_v1_stripped(VMSTest):
    """Test storage is used for analytics.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/78403
    """

    def _run(self, args, exit_stack):
        _test_storage_is_used_for_analytics(args.distrib_url, 'ubuntu22', False, 'v1', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v1_stripped().main())
