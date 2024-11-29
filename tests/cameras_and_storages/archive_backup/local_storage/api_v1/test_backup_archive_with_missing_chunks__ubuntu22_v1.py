# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.archive_backup.local_storage.api_v1.test_backup_archive_with_missing_chunks__ import _test_backup_archive_with_missing_chunks


class test_ubuntu22_v1(VMSTest):
    """Test backup archive with missing chunks.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/88922
    """

    def _run(self, args, exit_stack):
        _test_backup_archive_with_missing_chunks(args.distrib_url, 'ubuntu22', 'v1', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v1().main())
