# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import CloudTest
from tests.base_test import VMSTest
from tests.cloud.cloud_host.test_with_different_cloud_hosts_must_not_be_able_to_merge__ import _test_with_different_cloud_hosts_must_not_be_able_to_merge


class test_ubuntu22_ubuntu22_v0(VMSTest, CloudTest):
    """Test with different cloud hosts must not be able to merge.

    See: https://networkoptix.atlassian.net/browse/VMS-3730
    See: https://networkoptix.atlassian.net/wiki/display/SD/Merge+systems+test#Mergesystemstest-test_with_different_cloud_hosts_must_not_be_able_to_merge
    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_with_different_cloud_hosts_must_not_be_able_to_merge(args.cloud_host, args.distrib_url, ('ubuntu22', 'ubuntu22'), 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_ubuntu22_v0().main())
