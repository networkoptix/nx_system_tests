# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.merged_systems.test_bound_resource_count__ import _test_bound_resource_count


class test_ubuntu22_win11_v0(VMSTest):
    """Test bound resource count.

    See: https://networkoptix.atlassian.net/browse/FT-1047
    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_bound_resource_count(args.distrib_url, ('ubuntu22', 'win11'), 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_win11_v0().main())
