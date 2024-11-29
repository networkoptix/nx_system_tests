# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import CloudTest
from tests.base_test import VMSTest
from tests.cloud.merge.test_merge_cloud_systems_with_different_owners__ import _test_merge_cloud_systems_with_different_owners


class test_ubuntu22_ubuntu22_v2_settings_from_remote(VMSTest, CloudTest):
    """Test merge Cloud systems with different owners.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/6321
    """

    def _run(self, args, exit_stack):
        _test_merge_cloud_systems_with_different_owners(args.cloud_host, args.distrib_url, ('ubuntu22', 'ubuntu22'), 'v2', True, exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_ubuntu22_v2_settings_from_remote().main())