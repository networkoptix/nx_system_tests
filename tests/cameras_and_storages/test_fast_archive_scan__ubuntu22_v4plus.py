# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.test_fast_archive_scan__ import _test_fast_archive_scan


class test_ubuntu22_v4plus(VMSTest):
    """Test fast archive scan.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/27
    """

    def _run(self, args, exit_stack):
        _test_fast_archive_scan(args.distrib_url, 'ubuntu22', 'v4plus', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v4plus().main())