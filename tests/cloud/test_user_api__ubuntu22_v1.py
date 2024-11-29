# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import CloudTest
from tests.base_test import VMSTest
from tests.cloud.test_user_api__ import _test_cloud_users


class test_ubuntu22_v1(VMSTest, CloudTest):
    """Test cloud users.

    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_cloud_users(args.cloud_host, args.distrib_url, 'ubuntu22', 'v1', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v1().main())
