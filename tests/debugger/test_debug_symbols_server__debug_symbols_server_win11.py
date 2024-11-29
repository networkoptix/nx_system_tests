# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.debugger.test_debug_symbols_server__ import _test_debug_symbols_server


class test_debug_symbols_server_win11(VMSTest):

    def _run(self, args, exit_stack):
        _test_debug_symbols_server(args.distrib_url, 'win11', exit_stack)


if __name__ == '__main__':
    exit(test_debug_symbols_server_win11().main())
