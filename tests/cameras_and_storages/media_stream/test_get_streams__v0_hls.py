# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.media_stream.test_get_streams__ import _test_get_streams


class test_v0_hls(VMSTest):
    """Test get streams.

    Selection-Tag: gitlab
    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_get_streams(args.distrib_url, 'hls', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_v0_hls().main())
