# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.licences.test_change_license_deactivations_count__ import _test_change_license_deactivations_count


class test_win2019_v1(VMSTest):
    """Test change license deactivations count.

    Selection-Tag: gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/67037
    """

    def _run(self, args, exit_stack):
        _test_change_license_deactivations_count(args.distrib_url, 'win2019', 'v1', exit_stack)


if __name__ == '__main__':
    exit(test_win2019_v1().main())
