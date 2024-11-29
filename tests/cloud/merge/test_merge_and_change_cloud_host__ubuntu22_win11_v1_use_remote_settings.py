# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cloud.merge.test_merge_and_change_cloud_host__ import _test_merge_and_change_cloud_host


class test_ubuntu22_win11_v1_use_remote_settings(VMSTest):
    """Test merge and change Cloud host.

    Selection-Tag: gitlab
    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_merge_and_change_cloud_host(args.distrib_url, ('ubuntu22', 'win11'), 'v1', True, exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_win11_v1_use_remote_settings().main())
