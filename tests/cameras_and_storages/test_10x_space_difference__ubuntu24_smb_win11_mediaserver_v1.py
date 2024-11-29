# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.test_10x_space_difference__ import _test_10x_space_difference


class test_ubuntu24_smb_win11_mediaserver_v1(VMSTest):
    """Test 10x space difference.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/2801
    """

    def _run(self, args, exit_stack):
        _test_10x_space_difference(args.distrib_url, ('ubuntu24', 'win11'), 'v1', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu24_smb_win11_mediaserver_v1().main())