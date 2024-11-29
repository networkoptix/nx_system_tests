# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.merged_systems.failover.test_failover_by_storage__ import _test_storage_failover


class test_ubuntu22_ubuntu22_v0(VMSTest):
    """Test storage failover.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57207
    """

    def _run(self, args, exit_stack):
        _test_storage_failover(args.distrib_url, ('ubuntu22', 'ubuntu22'), 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_ubuntu22_v0().main())
