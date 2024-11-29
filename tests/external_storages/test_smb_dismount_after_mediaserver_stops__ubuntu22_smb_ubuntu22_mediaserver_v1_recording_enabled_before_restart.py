# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.external_storages.test_smb_dismount_after_mediaserver_stops__ import _test_dismount_nas_after_server_stopped


class test_ubuntu22_smb_ubuntu22_mediaserver_v1_recording_enabled_before_restart(VMSTest):
    """Test dismount nas after server stopped.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/2778
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/2779
    """

    def _run(self, args, exit_stack):
        _test_dismount_nas_after_server_stopped(args.distrib_url, ('ubuntu22', 'ubuntu22'), 'v1', True, exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_smb_ubuntu22_mediaserver_v1_recording_enabled_before_restart().main())
