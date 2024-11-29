# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.test_analytics_storage_out_of_space__ import _test_analytics_storage_out_of_space


class test_win11_v0(VMSTest):
    """Test analytics storage out of space.

    TODO: Test case must be updated after VMS-31172 and VMS-34784
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57370
    """

    def _run(self, args, exit_stack):
        _test_analytics_storage_out_of_space(args.distrib_url, 'win11', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_win11_v0().main())
