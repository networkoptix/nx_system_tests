# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.external_storages.test_smb_for_reserved_space__ import _test_nas_reserved_space


class test_ubuntu22_smb_win11_mediaserver_v1(VMSTest):
    """Test nas reserved space.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/6348
    """

    def _run(self, args, exit_stack):
        _test_nas_reserved_space(args.distrib_url, ('ubuntu22', 'win11'), 'v1', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_smb_win11_mediaserver_v1().main())
