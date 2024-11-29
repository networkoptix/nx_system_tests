# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import CloudTest
from tests.base_test import VMSTest
from tests.cloud.test_connect_disconnect__ import _test_connect_disconnect


class test_ubuntu22_v3(VMSTest, CloudTest):
    """Test connect disconnect.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/2122
    """

    def _run(self, args, exit_stack):
        _test_connect_disconnect(args.cloud_host, args.distrib_url, 'ubuntu22', 'v3', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v3().main())