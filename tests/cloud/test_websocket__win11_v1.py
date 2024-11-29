# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import CloudTest
from tests.base_test import VMSTest
from tests.cloud.test_websocket__ import _test_cloud_admin_cannot_open_websocket


class test_win11_v1(VMSTest, CloudTest):
    """Test cloud admin cannot open websocket.

    See: https://networkoptix.atlassian.net/browse/VMS-41385
    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_cloud_admin_cannot_open_websocket(args.cloud_host, args.distrib_url, 'win11', 'v1', exit_stack)


if __name__ == '__main__':
    exit(test_win11_v1().main())
