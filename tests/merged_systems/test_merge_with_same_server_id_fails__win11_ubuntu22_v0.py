# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.merged_systems.test_merge_with_same_server_id_fails__ import _test_cannot_merge_servers_with_same_id


class test_win11_ubuntu22_v0(VMSTest):
    """Test cannot merge servers with same id.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/47272
    """

    def _run(self, args, exit_stack):
        _test_cannot_merge_servers_with_same_id(args.distrib_url, ('win11', 'ubuntu22'), 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_win11_ubuntu22_v0().main())
