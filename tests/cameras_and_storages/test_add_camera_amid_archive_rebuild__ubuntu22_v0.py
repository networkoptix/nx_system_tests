# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.test_add_camera_amid_archive_rebuild__ import _test_add_camera_during_rebuild_archive


class test_ubuntu22_v0(VMSTest):
    """Test add camera during rebuild archive.

    Selection-Tag: gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/2085
    """

    def _run(self, args, exit_stack):
        _test_add_camera_during_rebuild_archive(args.distrib_url, 'ubuntu22', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v0().main())
