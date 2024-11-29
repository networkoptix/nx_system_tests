# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.test_mpjpeg_camera__ import _test_mpjpeg_camera


class test_ubuntu22_v0(VMSTest):
    """Test mpjpeg camera.

    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_mpjpeg_camera(args.distrib_url, 'ubuntu22', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v0().main())
