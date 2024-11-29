# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.merged_systems.test_merge_one_server__ import _test_merge_one_server_from_the_system


class test_merge_with_second_v4plus(VMSTest):
    """Test merge one server from the system.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/2080
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1590
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/81206
    """

    def _run(self, args, exit_stack):
        _test_merge_one_server_from_the_system(args.distrib_url, True, 'v4plus', exit_stack)


if __name__ == '__main__':
    exit(test_merge_with_second_v4plus().main())
