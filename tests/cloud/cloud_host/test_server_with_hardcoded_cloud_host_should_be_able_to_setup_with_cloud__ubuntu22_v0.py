# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import CloudTest
from tests.base_test import VMSTest
from tests.cloud.cloud_host.test_server_with_hardcoded_cloud_host_should_be_able_to_setup_with_cloud__ import _test_server_with_hardcoded_cloud_host_should_be_able_to_setup_with_cloud


class test_ubuntu22_v0(VMSTest, CloudTest):
    """Test get streams.

    Selection-Tag: no_testrail
    See: https://networkoptix.atlassian.net/wiki/spaces/SD/pages/85204446/Cloud+test
    """

    def _run(self, args, exit_stack):
        _test_server_with_hardcoded_cloud_host_should_be_able_to_setup_with_cloud(args.cloud_host, args.distrib_url, 'ubuntu22', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v0().main())
