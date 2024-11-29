# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.merged_systems.test_change_local_system_id__ import _test_change_local_system_id


class test_ubuntu22_win11_v0(VMSTest):
    """Test change local system id.

    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_change_local_system_id(args.distrib_url, ('ubuntu22', 'win11'), 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_win11_v0().main())
