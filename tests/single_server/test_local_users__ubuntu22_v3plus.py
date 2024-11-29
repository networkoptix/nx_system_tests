# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.test_local_users__ import _test_local_users


class test_ubuntu22_v3plus(VMSTest):
    """Test local users.

    Selection-Tag: gitlab
    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_local_users(args.distrib_url, 'ubuntu22', 'v3plus', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v3plus().main())
