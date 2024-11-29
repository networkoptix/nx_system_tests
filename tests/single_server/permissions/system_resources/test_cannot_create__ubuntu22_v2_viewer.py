# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.permissions.system_resources.test_cannot_create__ import _test_cannot_create


class test_ubuntu22_v2_viewer(VMSTest):
    """Test cannot create.

    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_cannot_create(args.distrib_url, 'ubuntu22', 'v2', 'viewer', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v2_viewer().main())
