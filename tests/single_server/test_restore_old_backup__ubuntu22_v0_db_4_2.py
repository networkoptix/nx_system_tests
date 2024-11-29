# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.test_restore_old_backup__ import _test_restore_from_old_version


class test_ubuntu22_v0_db_4_2(VMSTest):
    """Test restore from old version.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1681
    """

    def _run(self, args, exit_stack):
        _test_restore_from_old_version(args.distrib_url, 'ubuntu22', 'db', '4.2', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v0_db_4_2().main())
