# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import CloudTest
from tests.base_test import VMSTest
from tests.cloud.test_cloud_system_setup__ import _test_cloud_system_setup


class test_win11_v1(VMSTest, CloudTest):
    """Test get streams.

    Only Step 1 is automated.

    See: https://networkoptix.testrail.net/index.php?/cases/view/69624
    """

    def _run(self, args, exit_stack):
        _test_cloud_system_setup(args.cloud_host, args.distrib_url, 'win11', 'v1', exit_stack)


if __name__ == '__main__':
    exit(test_win11_v1().main())