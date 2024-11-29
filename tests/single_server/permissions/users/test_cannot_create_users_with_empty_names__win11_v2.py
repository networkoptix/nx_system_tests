# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.permissions.users.test_cannot_create_users_with_empty_names__ import _test_cannot_create_users_with_empty_names


class test_win11_v2(VMSTest):
    """Test cannot create users with empty names.

    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_cannot_create_users_with_empty_names(args.distrib_url, 'win11', 'v2', exit_stack)


if __name__ == '__main__':
    exit(test_win11_v2().main())
