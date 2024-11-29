# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.external_storages.test_iscsi__ import _test_iscsi


class test_win11_v0(VMSTest):
    """Test iscsi.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/19
    """

    def _run(self, args, exit_stack):
        _test_iscsi(args.distrib_url, 'win11', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_win11_v0().main())