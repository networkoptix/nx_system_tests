# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.external_storages.test_smb_dismount_while_mediaserver_works__ import _test_dismount_nas_while_server_is_working


class test_ubuntu22_smb_ubuntu22_mediaserver_v0(VMSTest):
    """Test dismount nas while server is working.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/2777
    """

    def _run(self, args, exit_stack):
        _test_dismount_nas_while_server_is_working(args.distrib_url, ('ubuntu22', 'ubuntu22'), 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_smb_ubuntu22_mediaserver_v0().main())
