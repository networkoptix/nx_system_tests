# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.vms_benchmark.test_autodiscovered_testcamera__ import _test_autodiscovered_testcamera


class test_ubuntu22_v4plus(VMSTest):
    """Test autodiscovered testcamera.

    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_autodiscovered_testcamera(args.distrib_url, 'ubuntu22', 'v4plus', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v4plus().main())
