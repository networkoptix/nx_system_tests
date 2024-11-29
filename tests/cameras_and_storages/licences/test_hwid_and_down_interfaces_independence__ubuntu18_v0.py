# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.licences.test_hwid_and_down_interfaces_independence__ import _test_hwid_and_down_interfaces_independence


class test_ubuntu18_v0(VMSTest):
    """Test hwid and down interfaces independence.

    Selection-Tag: gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/712
    """

    def _run(self, args, exit_stack):
        _test_hwid_and_down_interfaces_independence(args.distrib_url, 'ubuntu18', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu18_v0().main())
