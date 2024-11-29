# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.test_saved_media_should_appear_after_archive_is_rebuilt__ import _test_saved_media_should_appear_after_archive_is_rebuilt


class test_ubuntu22_v0(VMSTest):
    """Test saved media should appear after archive is rebuilt.

    Selection-Tag: no_testrail
    Selection-Tag: gitlab
    """

    def _run(self, args, exit_stack):
        _test_saved_media_should_appear_after_archive_is_rebuilt(args.distrib_url, 'ubuntu22', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v0().main())
