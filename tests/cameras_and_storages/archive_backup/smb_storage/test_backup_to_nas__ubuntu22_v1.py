# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.archive_backup.smb_storage.test_backup_to_nas__ import _test_backup_to_nas


class test_ubuntu22_v1(VMSTest):
    """Test backup to nas.

    Selection-Tag: gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/2755
    """

    def _run(self, args, exit_stack):
        _test_backup_to_nas(args.distrib_url, ('ubuntu22', 'ubuntu22'), 'v1', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v1().main())
