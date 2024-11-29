# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.merged_systems.time_synchronization.test_secondary_server_temporary_inet_on__ import _test_secondary_server_temporary_inet_on


class test_ubuntu22_ubuntu22_v0(VMSTest):
    """Test secondary server temporary inet on.

    Selection-Tag: gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1605
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/15863
    """

    def _run(self, args, exit_stack):
        _test_secondary_server_temporary_inet_on(args.distrib_url, ('ubuntu22', 'ubuntu22'), 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_ubuntu22_v0().main())
