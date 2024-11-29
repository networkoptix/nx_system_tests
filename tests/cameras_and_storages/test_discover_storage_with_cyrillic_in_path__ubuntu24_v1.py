# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.test_discover_storage_with_cyrillic_in_path__ import _test_discover_storage_with_cyrillic_in_path


class test_ubuntu24_v1(VMSTest):
    """Test discover storage with cyrillic in path.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/79188
    """

    def _run(self, args, exit_stack):
        _test_discover_storage_with_cyrillic_in_path(args.distrib_url, 'ubuntu24', 'v1', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu24_v1().main())
