# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.test_session_survives_restart__ import _test_session_survives_restart


class test_ubuntu22_v1(VMSTest):
    """Test session survives restart.

    See: https://networkoptix.atlassian.net/browse/VMS-20920
    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_session_survives_restart(args.distrib_url, 'ubuntu22', 'v1', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v1().main())
