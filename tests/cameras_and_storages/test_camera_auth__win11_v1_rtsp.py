# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.test_camera_auth__ import _test_camera_auth


class test_win11_v1_rtsp(VMSTest):
    """Test camera auth.

    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_camera_auth(args.distrib_url, 'win11', 'v1', 'rtsp_mjpeg', exit_stack)


if __name__ == '__main__':
    exit(test_win11_v1_rtsp().main())
