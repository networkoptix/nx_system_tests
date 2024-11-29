# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cloud.test_cloud_host_patching__ import _test_set_cloud_host


class test_ubuntu22_v0(VMSTest):
    """Test set cloud host.

    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_set_cloud_host(args.distrib_url, 'ubuntu22', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v0().main())
