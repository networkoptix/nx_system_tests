# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.test_discovery__ import _test_discovery


class test_win11_v1(VMSTest):
    """Test discovery.

    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_discovery(args.distrib_url, 'win11', 'v1', exit_stack)


if __name__ == '__main__':
    exit(test_win11_v1().main())