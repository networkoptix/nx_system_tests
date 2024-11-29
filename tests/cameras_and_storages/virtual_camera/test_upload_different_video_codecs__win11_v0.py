# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.virtual_camera.test_upload_different_video_codecs__ import _test_upload_different_video_codecs


class test_win11_v0(VMSTest):
    """Test upload different video codecs.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/43013
    """

    def _run(self, args, exit_stack):
        _test_upload_different_video_codecs(args.distrib_url, 'win11', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_win11_v0().main())
