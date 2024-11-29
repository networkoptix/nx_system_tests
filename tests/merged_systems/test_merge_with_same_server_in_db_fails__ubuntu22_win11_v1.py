# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.merged_systems.test_merge_with_same_server_in_db_fails__ import _test_cannot_merge_systems_with_same_server


class test_ubuntu22_win11_v1(VMSTest):
    """Test cannot merge systems with same server.

    Selection-Tag: gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/47273
    """

    def _run(self, args, exit_stack):
        _test_cannot_merge_systems_with_same_server(args.distrib_url, ('ubuntu22', 'win11'), 'v1', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_win11_v1().main())
