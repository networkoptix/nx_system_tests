# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.logging.test_log_level_specific_values__ import _test_log_level_specific_values


class test_win11_v0_default(VMSTest):
    """Test log level specific values.

    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_log_level_specific_values(
            args.distrib_url,
            'win11',
            None,
            'info',
            'v0',
            exit_stack,
            )


if __name__ == '__main__':
    exit(test_win11_v0_default().main())
