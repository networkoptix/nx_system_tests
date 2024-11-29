# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.permissions.system_resources.test_cannot_remove__ import _test_cannot_remove


class test_ubuntu22_v0_advanced_viewer(VMSTest):
    """Test cannot remove.

    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_cannot_remove(args.distrib_url, 'ubuntu22', 'v0', 'advanced_viewer', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v0_advanced_viewer().main())