# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.logging.test_log_level_specific_values__ import _test_log_level_specific_values


class test_ubuntu22_v0_commas(VMSTest):
    """Test log level specific values.

    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_log_level_specific_values(
            args.distrib_url,
            'ubuntu22',
            'info,debug[nx::network],verbose[nx::utils,nx::mediaserver]',
            'info, debug[nx::network], verbose[nx::mediaserver,nx::utils]',
            'v0',
            exit_stack,
            )


if __name__ == '__main__':
    exit(test_ubuntu22_v0_commas().main())
