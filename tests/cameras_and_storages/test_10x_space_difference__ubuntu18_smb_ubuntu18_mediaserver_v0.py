# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.test_10x_space_difference__ import _test_10x_space_difference


class test_ubuntu18_smb_ubuntu18_mediaserver_v0(VMSTest):
    """Test 10x space difference.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/2801
    """

    def _run(self, args, exit_stack):
        _test_10x_space_difference(args.distrib_url, ('ubuntu18', 'ubuntu18'), 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu18_smb_ubuntu18_mediaserver_v0().main())
