# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.external_storages.test_smb_after_archive_rebuild__ import _test_nas_archive_after_rebuild


class test_ubuntu22_smb_ubuntu22_mediaserver_v4plus(VMSTest):
    """Test nas archive after rebuild.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/2782
    """

    def _run(self, args, exit_stack):
        _test_nas_archive_after_rebuild(args.distrib_url, ('ubuntu22', 'ubuntu22'), 'v4plus', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_smb_ubuntu22_mediaserver_v4plus().main())
