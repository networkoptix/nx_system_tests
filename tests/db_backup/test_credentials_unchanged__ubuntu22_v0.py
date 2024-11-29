# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.db_backup.test_credentials_unchanged__ import _test_credentials_unchanged_after_restore


class test_ubuntu22_v0(VMSTest):
    """Test credentials unchanged after restore.

    Selection-Tag: gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1678
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/2053
    """

    def _run(self, args, exit_stack):
        _test_credentials_unchanged_after_restore(args.distrib_url, 'ubuntu22', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v0().main())
