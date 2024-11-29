# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import CloudTest
from tests.base_test import VMSTest
from tests.cloud.cloud_host.test_with_different_cloud_hosts_must_not_be_able_to_merge__ import _test_with_different_cloud_hosts_must_not_be_able_to_merge


class test_ubuntu22_win11_v1(VMSTest, CloudTest):
    """Test with different cloud hosts must not be able to merge.

    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_with_different_cloud_hosts_must_not_be_able_to_merge(args.cloud_host, args.distrib_url, ('ubuntu22', 'win11'), 'v1', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_win11_v1().main())
