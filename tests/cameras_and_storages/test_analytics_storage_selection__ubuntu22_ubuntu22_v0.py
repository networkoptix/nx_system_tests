# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.test_analytics_storage_selection__ import _test_biggest_local_disk_is_chosen


class test_ubuntu22_ubuntu22_v0(VMSTest):
    """Test biggest local disk is chosen.

    TODO: Test case must be updated after VMS-31172 and VMS-34784
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57373
    """

    def _run(self, args, exit_stack):
        _test_biggest_local_disk_is_chosen(args.distrib_url, ('ubuntu22', 'ubuntu22'), 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_ubuntu22_v0().main())
