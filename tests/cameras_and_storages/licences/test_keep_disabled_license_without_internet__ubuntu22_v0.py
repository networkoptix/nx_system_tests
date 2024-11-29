# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.licences.test_keep_disabled_license_without_internet__ import _test_keep_disabled_license_without_internet


class test_ubuntu22_v0(VMSTest):
    """Test keep disabled license without internet.

    Selection-Tag: gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/16588
    """

    def _run(self, args, exit_stack):
        _test_keep_disabled_license_without_internet(args.distrib_url, 'ubuntu22', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v0().main())
