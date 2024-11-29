# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.event_rules.test_omit_db_logging__ import _test_omit_db_logging


class test_win11_v0(VMSTest):
    """Test omit db logging.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57256
    """

    def _run(self, args, exit_stack):
        _test_omit_db_logging(args.distrib_url, 'win11', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_win11_v0().main())
