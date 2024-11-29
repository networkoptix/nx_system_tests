# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.test_reserved_space_on_storage__ import _test_reserved_space


class test_ubuntu22_v0_sata(VMSTest):
    """Test reserved space.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/6347
    """

    def _run(self, args, exit_stack):
        _test_reserved_space(args.distrib_url, 'ubuntu22', 'sata', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v0_sata().main())
