# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.vms_tools.test_vms_benchmark__ import _test_vms_benchmark_installation


class test_ubuntu22(VMSTest):
    """Test vms benchmark installation.

    Selection-Tag: gitlab
    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_vms_benchmark_installation(args.distrib_url, 'ubuntu22', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22().main())
