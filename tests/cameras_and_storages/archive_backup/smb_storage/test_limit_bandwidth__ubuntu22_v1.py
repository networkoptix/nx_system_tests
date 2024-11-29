# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.archive_backup.smb_storage.test_limit_bandwidth__ import _test_limit_bandwidth


class test_ubuntu22_v1(VMSTest):
    """Test limit bandwidth.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/2742
    """

    def _run(self, args, exit_stack):
        _test_limit_bandwidth(args.distrib_url, ('ubuntu22', 'ubuntu22'), 'v1', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v1().main())
