# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.test_media_database__ import _test_restore_corrupted_db


class test_win11_v0(VMSTest):
    """Test restore corrupted db.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/6759
    Selection-Tag: gitlab
    """

    def _run(self, args, exit_stack):
        _test_restore_corrupted_db(args.distrib_url, 'win11', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_win11_v0().main())