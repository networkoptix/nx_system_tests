# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.archive_backup.local_storage.test_rebuild_archive_for_backup_storage__ import _test_rebuild_archive_for_backup_storage


class test_win11_v2(VMSTest):
    """Test rebuild archive for backup storage.

    Selection-Tag: gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/26
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/24
    """

    def _run(self, args, exit_stack):
        _test_rebuild_archive_for_backup_storage(args.distrib_url, 'win11', 'v2', exit_stack)


if __name__ == '__main__':
    exit(test_win11_v2().main())
