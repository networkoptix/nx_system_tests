# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.archive_rewrite.test_archive_rewrite_with_one_storage_disabled__ import _test_archive_rewrite_with_one_storage_disabled


class test_win2019_v0(VMSTest):
    """Test archive rewrite with one storage disabled.

    Selection-Tag: gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/6760
    """

    def _run(self, args, exit_stack):
        _test_archive_rewrite_with_one_storage_disabled(args.distrib_url, 'win2019', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_win2019_v0().main())