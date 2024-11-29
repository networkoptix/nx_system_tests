# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.archive_backup.local_storage.api_v1.test_low_quality_only__ import _test_low_quality_only


class test_win11_v1(VMSTest):
    """Test low quality only.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/85875
    """

    def _run(self, args, exit_stack):
        _test_low_quality_only(args.distrib_url, 'win11', 'v1', exit_stack)


if __name__ == '__main__':
    exit(test_win11_v1().main())
