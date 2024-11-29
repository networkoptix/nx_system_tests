# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.media_stream.test_get_streams__ import _test_get_streams


class test_v0_rtsp(VMSTest):
    """Test get streams.

    Selection-Tag: gitlab
    Selection-Tag: no_testrail
    See: https://networkoptix.atlassian.net/wiki/spaces/SD/pages/23920653/Connection+behind+NAT#ConnectionbehindNAT-test_get_streams
    """

    def _run(self, args, exit_stack):
        _test_get_streams(args.distrib_url, 'rtsp', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_v0_rtsp().main())
