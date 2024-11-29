# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.logging.test_log_level_by_namespace__ import _test_log_level_by_namespace


class test_win11_v0(VMSTest):
    """Test log level by namespace.

    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_log_level_by_namespace(args.distrib_url, 'win11', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_win11_v0().main())
