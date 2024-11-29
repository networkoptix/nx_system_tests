# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.archive_backup.local_storage.api_v1.test_low_quality_for_new_added_cameras__ import _test_low_quality_for_new_added_cameras


class test_ubuntu22_ubuntu22_v1(VMSTest):
    """Test low quality for new added cameras.

    Selection-Tag: gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/85883
    """

    def _run(self, args, exit_stack):
        _test_low_quality_for_new_added_cameras(args.distrib_url, ('ubuntu22', 'ubuntu22'), 'v1', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_ubuntu22_v1().main())
