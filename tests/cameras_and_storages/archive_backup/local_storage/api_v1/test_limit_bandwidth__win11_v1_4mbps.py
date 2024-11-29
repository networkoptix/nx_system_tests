# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.archive_backup.local_storage.api_v1.test_limit_bandwidth__ import _test_limit_bandwidth


class test_win11_v1_4mbps(VMSTest):
    """Test limit bandwidth.

    Selection-Tag: gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/2742
    """

    def _run(self, args, exit_stack):
        _test_limit_bandwidth(args.distrib_url, 'win11', 4, 'v1', exit_stack)


if __name__ == '__main__':
    exit(test_win11_v1_4mbps().main())
