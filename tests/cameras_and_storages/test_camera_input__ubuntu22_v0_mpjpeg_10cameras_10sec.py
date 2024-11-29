# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.test_camera_input__ import _test_camera_input


class test_ubuntu22_v0_mpjpeg_10cameras_10sec(VMSTest):
    """Test camera input.

    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_camera_input(args.distrib_url, 'ubuntu22', 'v0', 10, 10, True, 'mpjpeg', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v0_mpjpeg_10cameras_10sec().main())
