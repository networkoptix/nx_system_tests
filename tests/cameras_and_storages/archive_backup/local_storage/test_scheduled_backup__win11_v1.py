# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.archive_backup.local_storage.test_scheduled_backup__ import _test_scheduled_backup


class test_win11_v1(VMSTest):
    """Test scheduled backup.

    Selection-Tag: gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/2739
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/78230
    """

    def _run(self, args, exit_stack):
        _test_scheduled_backup(args.distrib_url, 'win11', 'v1', exit_stack)


if __name__ == '__main__':
    exit(test_win11_v1().main())
