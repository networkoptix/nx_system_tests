# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.zfs_storages.test_record_from_camera__ import _test_record_from_camera


class test_ubuntu22_v0_mirrored(VMSTest):
    """Test record from camera.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/78403
    """

    def _run(self, args, exit_stack):
        _test_record_from_camera(args.distrib_url, 'ubuntu22', True, 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v0_mirrored().main())
