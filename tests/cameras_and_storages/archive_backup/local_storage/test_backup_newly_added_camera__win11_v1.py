# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.archive_backup.local_storage.test_backup_newly_added_camera__ import _test_backup_newly_added_camera


class test_win11_v1(VMSTest):
    """Test backup newly added camera.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/2734
    Selection-Tag: gitlab
    """

    def _run(self, args, exit_stack):
        _test_backup_newly_added_camera(args.distrib_url, 'win11', 'v1', exit_stack)


if __name__ == '__main__':
    exit(test_win11_v1().main())
