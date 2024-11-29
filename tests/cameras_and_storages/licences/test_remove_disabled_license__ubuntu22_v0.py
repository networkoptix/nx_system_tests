# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.licences.test_remove_disabled_license__ import _test_remove_disabled_license


class test_ubuntu22_v0(VMSTest):
    """Test remove disabled license.

    Selection-Tag: gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/16586
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/69627
    """

    def _run(self, args, exit_stack):
        _test_remove_disabled_license(args.distrib_url, 'ubuntu22', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v0().main())
