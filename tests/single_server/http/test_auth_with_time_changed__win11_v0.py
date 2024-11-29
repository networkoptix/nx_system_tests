# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.http.test_auth_with_time_changed__ import _test_auth_with_time_changed


class test_win11_v0(VMSTest):
    """Test auth with time changed.

    See: https://networkoptix.atlassian.net/browse/VMS-7775
    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_auth_with_time_changed(args.distrib_url, 'win11', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_win11_v0().main())
