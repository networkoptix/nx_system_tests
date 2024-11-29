# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.external_storages.test_smb_user_disabled__ import _test_disabled_smb_user


class test_win11_win2019_v1(VMSTest):
    """Test disabled smb user.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/81602
    """

    def _run(self, args, exit_stack):
        _test_disabled_smb_user(args.distrib_url, ('win11', 'win2019'), 'v1', exit_stack)


if __name__ == '__main__':
    exit(test_win11_win2019_v1().main())
