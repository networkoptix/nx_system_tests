# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.audit_log.test_audit_log_expired__ import _test_audit_log_expired


class test_win11_v1(VMSTest):
    """Test audit log expired.

    Selection-Tag: gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/6725
    """

    def _run(self, args, exit_stack):
        _test_audit_log_expired(args.distrib_url, 'win11', 'v1', exit_stack)


if __name__ == '__main__':
    exit(test_win11_v1().main())
