# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.merged_systems.test_level_setting__ import _test_level_setting


class test_ubuntu22_win11_v2(VMSTest):
    """Test level setting.

    Selection-Tag: no_testrail
    See: https://networkoptix.atlassian.net/browse/FT-1864
    Selection-Tag: gitlab
    """

    def _run(self, args, exit_stack):
        _test_level_setting(args.distrib_url, ('ubuntu22', 'win11'), 'v2', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_win11_v2().main())
