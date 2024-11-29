# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.media_stream.test_media_stream_should_be_loaded_correctly__ import _test_media_stream_should_be_loaded_correctly


class test_ubuntu22_v0_rtsp(VMSTest):
    """Test media stream should be loaded correctly.

    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_media_stream_should_be_loaded_correctly(args.distrib_url, 'ubuntu22', 'rtsp', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v0_rtsp().main())
