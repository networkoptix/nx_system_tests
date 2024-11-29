# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.licences.test_remove_deactivated_license__ import _test_remove_deactivated_license


class test_win11_v1(VMSTest):
    """Test remove deactivated license.

    Selection-Tag: gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/16587
    """

    def _run(self, args, exit_stack):
        _test_remove_deactivated_license(args.distrib_url, 'win11', 'v1', exit_stack)


if __name__ == '__main__':
    exit(test_win11_v1().main())
