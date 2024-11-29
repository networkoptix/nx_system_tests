# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.test_change_admin_password_through_config__ import _test_change_admin_password_through_config


class test_ubuntu22_v0(VMSTest):
    """Test change admin password through config.

    Selection-Tag: gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/6308
    """

    def _run(self, args, exit_stack):
        _test_change_admin_password_through_config(args.distrib_url, 'ubuntu22', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v0().main())