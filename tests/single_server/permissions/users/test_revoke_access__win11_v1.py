# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.permissions.users.test_revoke_access__ import _test_revoke_access


class test_win11_v1(VMSTest):
    """Test revoke access.

    See: https://networkoptix.atlassian.net/browse/FT-1140
    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_revoke_access(args.distrib_url, 'win11', 'v1', exit_stack)


if __name__ == '__main__':
    exit(test_win11_v1().main())
