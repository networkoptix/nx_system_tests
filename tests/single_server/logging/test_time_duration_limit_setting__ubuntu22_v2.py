# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.logging.test_time_duration_limit_setting__ import _test_time_duration_limit_setting


class test_ubuntu22_v2(VMSTest):
    """Test time duration limit setting.

    Selection-Tag: gitlab
    Selection-Tag: no_testrail
    See: https://networkoptix.atlassian.net/browse/FT-1864
    """

    def _run(self, args, exit_stack):
        _test_time_duration_limit_setting(args.distrib_url, 'ubuntu22', 'v2', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v2().main())
