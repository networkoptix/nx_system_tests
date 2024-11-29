# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.http.test_http_header_server__ import _test_http_header_server


class test_win11_v0(VMSTest):
    """Test http header server.

    See: https://networkoptix.atlassian.net/browse/VMS-3068
    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_http_header_server(args.distrib_url, 'win11', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_win11_v0().main())
