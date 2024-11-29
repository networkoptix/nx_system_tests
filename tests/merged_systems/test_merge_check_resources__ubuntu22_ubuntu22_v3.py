# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.merged_systems.test_merge_check_resources__ import _test_merge_resources


class test_ubuntu22_ubuntu22_v3(VMSTest):
    """Check users, layouts, servers and cameras after merge.

    Selection-Tag: gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1594
    """

    def _run(self, args, exit_stack):
        _test_merge_resources(args.distrib_url, ('ubuntu22', 'ubuntu22'), 'v3', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_ubuntu22_v3().main())
