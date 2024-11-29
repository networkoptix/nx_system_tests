# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.vms_benchmark.test_manually_added_testcamera__ import _test_manually_added_testcamera


class test_v4(VMSTest):
    """Test manually added testcamera.

    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_manually_added_testcamera(args.distrib_url, 'v4plus', exit_stack)


if __name__ == '__main__':
    exit(test_v4().main())
