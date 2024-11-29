# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.ldap_external.test_session_expiration__ import _test_session_expiration


class test_ubuntu22_v1(VMSTest):
    """Test session expiration.

    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_session_expiration(args.distrib_url, 'ubuntu22', 'v1', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v1().main())
