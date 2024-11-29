# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import CloudTest
from tests.base_test import VMSTest
from tests.cloud.cloud_host.test_server_with_hardcoded_cloud_host_should_be_able_to_setup_with_cloud__ import _test_server_with_hardcoded_cloud_host_should_be_able_to_setup_with_cloud


class test_win11_v1(VMSTest, CloudTest):
    """Test server with hardcoded cloud host should be able to setup with cloud.

    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_server_with_hardcoded_cloud_host_should_be_able_to_setup_with_cloud(args.cloud_host, args.distrib_url, 'win11', 'v1', exit_stack)


if __name__ == '__main__':
    exit(test_win11_v1().main())
