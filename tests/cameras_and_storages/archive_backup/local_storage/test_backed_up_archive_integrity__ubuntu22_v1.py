# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.archive_backup.local_storage.test_backed_up_archive_integrity__ import _test_backed_up_archive_integrity


class test_ubuntu22_v1(VMSTest):
    """Test backed up archive integrity.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/2736
    Selection-Tag: gitlab
    """

    def _run(self, args, exit_stack):
        _test_backed_up_archive_integrity(args.distrib_url, 'ubuntu22', 'v1', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v1().main())
