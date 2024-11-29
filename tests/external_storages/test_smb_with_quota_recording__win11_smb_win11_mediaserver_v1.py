# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.external_storages.test_smb_with_quota_recording__ import _test_share_with_quota


class test_win11_smb_win11_mediaserver_v1(VMSTest):
    """Test share with quota.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/43041
    """

    def _run(self, args, exit_stack):
        _test_share_with_quota(args.distrib_url, ('win11', 'win11'), 'v1', exit_stack)


if __name__ == '__main__':
    exit(test_win11_smb_win11_mediaserver_v1().main())
