# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.rest_api.test_auth_key_blatantly_wrong__ import _test_auth_key_blatantly_wrong


class test_win11_v0(VMSTest):
    """Test auth key blatantly wrong.

    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_auth_key_blatantly_wrong(args.distrib_url, 'win11', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_win11_v0().main())
