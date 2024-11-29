# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.test_dummy_server__ import _test_dummy_server


class test_win11_v1(VMSTest):
    """Test dummy server.

    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_dummy_server(args.distrib_url, 'win11', 'v1', exit_stack)


if __name__ == '__main__':
    exit(test_win11_v1().main())
