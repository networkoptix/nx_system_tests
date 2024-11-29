# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.ldap.test_server_disconnect__ import _test_server_disconnect


class test_win11(VMSTest):

    def _run(self, args, exit_stack):
        _test_server_disconnect(args.distrib_url, 'win11', exit_stack)


if __name__ == '__main__':
    exit(test_win11().main())
