# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.external_storages.test_smb_add_change_remove__ import _test_add_change_and_remove_external_storage


class test_win11_v0(VMSTest):
    """Test add change and remove external storage.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/2075
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/2076
    """

    def _run(self, args, exit_stack):
        _test_add_change_and_remove_external_storage(args.distrib_url, 'win11', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_win11_v0().main())
