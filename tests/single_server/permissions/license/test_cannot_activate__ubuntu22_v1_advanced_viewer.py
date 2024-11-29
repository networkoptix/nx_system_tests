# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.permissions.license.test_cannot_activate__ import _test_cannot_activate


class test_ubuntu22_v1_advanced_viewer(VMSTest):
    """Test cannot activate.

    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_cannot_activate(args.distrib_url, 'ubuntu22', 'v1', 'advanced_viewer', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v1_advanced_viewer().main())
