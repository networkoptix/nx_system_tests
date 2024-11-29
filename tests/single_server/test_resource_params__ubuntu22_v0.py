# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.test_resource_params__ import _test_remove_child_resources


class test_ubuntu22_v0(VMSTest):
    """Test remove child resources.

    See: https://networkoptix.atlassian.net/browse/VMS-2246
    See: https://networkoptix.atlassian.net/browse/VMS-2904
    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_remove_child_resources(args.distrib_url, 'ubuntu22', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v0().main())
