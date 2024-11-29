# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.external_storages.test_smb_password_not_in_logs_and_db__ import _test_no_password_in_logs_and_db


class test_ubuntu22_smb_ubuntu22_mediaserver_v0(VMSTest):
    """Test no password in logs and db.

    Selection-Tag: gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/43058
    """

    def _run(self, args, exit_stack):
        _test_no_password_in_logs_and_db(args.distrib_url, ('ubuntu22', 'ubuntu22'), 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_smb_ubuntu22_mediaserver_v0().main())
