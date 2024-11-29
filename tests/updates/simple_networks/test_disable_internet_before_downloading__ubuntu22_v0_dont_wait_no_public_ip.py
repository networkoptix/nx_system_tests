# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.updates.simple_networks.test_disable_internet_before_downloading__ import _test_disable_internet_before_downloading


class test_ubuntu22_v0_dont_wait_no_public_ip(VMSTest):
    """Test disable internet before downloading.

    Selection-Tag: gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57937
    """

    def _run(self, args, exit_stack):
        _test_disable_internet_before_downloading(args.distrib_url, ('ubuntu22', 'ubuntu22'), 'v0', True, exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v0_dont_wait_no_public_ip().main())
