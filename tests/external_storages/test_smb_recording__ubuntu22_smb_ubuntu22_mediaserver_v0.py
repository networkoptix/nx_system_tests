# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.external_storages.test_smb_recording__ import _test_record_on_remote


class test_ubuntu22_smb_ubuntu22_mediaserver_v0(VMSTest):
    """Test record on remote.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/69629
    Selection-Tag: gitlab
    """

    def _run(self, args, exit_stack):
        _test_record_on_remote(args.distrib_url, ('ubuntu22', 'ubuntu22'), 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_smb_ubuntu22_mediaserver_v0().main())
