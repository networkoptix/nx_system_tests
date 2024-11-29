# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.audit_log.test_rename_server__ import _test_rename_server


class test_ubuntu22_v4plus(VMSTest):
    """Test rename server.

    Selection-Tag: gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/2077
    """

    def _run(self, args, exit_stack):
        _test_rename_server(args.distrib_url, 'ubuntu22', 'v4plus', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v4plus().main())
