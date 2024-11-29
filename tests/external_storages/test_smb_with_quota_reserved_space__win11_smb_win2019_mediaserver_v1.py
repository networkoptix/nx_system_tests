# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.external_storages.test_smb_with_quota_reserved_space__ import _test_nas_reserved_space_with_quota_enabled


class test_win11_smb_win2019_mediaserver_v1(VMSTest):
    """Test nas reserved space with quota enabled.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/43040
    """

    def _run(self, args, exit_stack):
        _test_nas_reserved_space_with_quota_enabled(args.distrib_url, ('win11', 'win2019'), 'v1', exit_stack)


if __name__ == '__main__':
    exit(test_win11_smb_win2019_mediaserver_v1().main())
