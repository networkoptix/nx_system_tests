# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.test_save_and_remove_layout__ import _test_save_and_remove_layout


class test_ubuntu22_v0(VMSTest):
    """Test save and remove layout.

    Selection-Tag: gitlab
    See: https://networkoptix.atlassian.net/browse/VMS-10717
    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_save_and_remove_layout(args.distrib_url, 'ubuntu22', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v0().main())
