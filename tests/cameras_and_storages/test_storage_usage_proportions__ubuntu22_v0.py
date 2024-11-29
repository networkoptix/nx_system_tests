# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.test_storage_usage_proportions__ import _test_storage_usage_proportions


class test_ubuntu22_v0(VMSTest):
    """Test storage usage proportions.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/6776
    Selection-Tag: gitlab
    """

    def _run(self, args, exit_stack):
        _test_storage_usage_proportions(args.distrib_url, 'ubuntu22', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v0().main())
