# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import CloudTest
from tests.base_test import VMSTest
from tests.cloud.merge.test_merge_cloud_systems_with_same_owner__ import _test_merge_cloud_systems_with_same_owner


class test_ubuntu22_win11_v1_settings_from_local(VMSTest, CloudTest):
    """Test merge cloud systems with same owner.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/6722
    """

    def _run(self, args, exit_stack):
        _test_merge_cloud_systems_with_same_owner(args.cloud_host, args.distrib_url, ('ubuntu22', 'win11'), 'v1', False, exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_win11_v1_settings_from_local().main())
