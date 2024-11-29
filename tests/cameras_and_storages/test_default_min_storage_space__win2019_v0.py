# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.test_default_min_storage_space__ import _test_default_min_storage_space


class test_win2019_v0(VMSTest):
    """Test default min storage space.

    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_default_min_storage_space(args.distrib_url, 'win2019', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_win2019_v0().main())
