# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import CloudTest
from tests.base_test import VMSTest
from tests.cloud.cloud_host.test_setup_cloud_system_enable_internet_after_start__ import _test_setup_cloud_system_enable_internet_after_start


class test_ubuntu22_v0(VMSTest, CloudTest):
    """Test setup cloud system enable internet after start.

    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_setup_cloud_system_enable_internet_after_start(args.cloud_host, args.distrib_url, 'ubuntu22', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v0().main())
