# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.merged_systems.test_auth_session_shared_between_two_mediaservers__ import _test_shared_local_session


class test_ubuntu22_ubuntu22_v1(VMSTest):
    """Test shared local session.

    See: https://networkoptix.atlassian.net/browse/FT-1567
    See: https://networkoptix.atlassian.net/browse/FT-1679
    Selection-Tag: no_testrail
    Selection-Tag: gitlab
    """

    def _run(self, args, exit_stack):
        _test_shared_local_session(args.distrib_url, ('ubuntu22', 'ubuntu22'), 'v1', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_ubuntu22_v1().main())
