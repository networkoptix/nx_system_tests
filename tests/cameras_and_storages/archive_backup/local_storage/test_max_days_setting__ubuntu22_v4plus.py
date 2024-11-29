# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.archive_backup.local_storage.test_max_days_setting__ import _test_max_days_setting


class test_ubuntu22_v4plus(VMSTest):
    """Test max days setting.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/2754
    Selection-Tag: gitlab
    """

    def _run(self, args, exit_stack):
        _test_max_days_setting(args.distrib_url, 'ubuntu22', 'v4plus', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v4plus().main())
