# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.merged_systems.test_message_bus__ import _test_message_bus_with_local_system


class test_ubuntu22_win11_v0(VMSTest):
    """Test message bus with local system.

    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_message_bus_with_local_system(args.distrib_url, ('ubuntu22', 'win11'), 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_win11_v0().main())
