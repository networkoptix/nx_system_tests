# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.archive_backup.local_storage.api_v1.test_skip_current_queue_for_camera_with_disabled_backup__ import _test_skip_current_queue_for_camera_with_disabled_backup


class test_ubuntu22_v1(VMSTest):
    """Test skip current queue for camera with disabled backup.

    Selection-Tag: gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/85914
    """

    def _run(self, args, exit_stack):
        _test_skip_current_queue_for_camera_with_disabled_backup(args.distrib_url, 'ubuntu22', 'v1', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v1().main())
