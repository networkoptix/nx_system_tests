# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.archive_backup.local_storage.api_v1.test_bookmark_changing_after_skip_current_queue__ import _test_bookmark_changing_after_skip_current_queue


class test_ubuntu22_v1(VMSTest):
    """Test bookmark changing after skip current queue.

    Selection-Tag: gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/88914
    """

    def _run(self, args, exit_stack):
        _test_bookmark_changing_after_skip_current_queue(args.distrib_url, 'ubuntu22', 'v1', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v1().main())
