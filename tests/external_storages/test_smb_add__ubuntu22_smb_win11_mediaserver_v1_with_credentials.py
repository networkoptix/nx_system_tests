# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.external_storages.test_smb_add__ import _test_add_storage


class test_ubuntu22_smb_win11_mediaserver_v1_with_credentials(VMSTest):
    """Test add storage.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/6755
    """

    def _run(self, args, exit_stack):
        _test_add_storage(args.distrib_url, ('ubuntu22', 'win11'), 'v1', ('UserWithPassword', 'GoodPassword'), exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_smb_win11_mediaserver_v1_with_credentials().main())
