# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.merged_systems.test_auth_session_expiration_closes_connection__ import _test_close_connection_on_session_expiration


class test_win11_v1_wait_to_expire_mpjpeg(VMSTest):
    """Test close connection on session expiration.

    Selection-Tag: gitlab
    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_close_connection_on_session_expiration(args.distrib_url, ('win11', 'win11'), 'v1', None, 'mpjpeg', exit_stack)


if __name__ == '__main__':
    exit(test_win11_v1_wait_to_expire_mpjpeg().main())
