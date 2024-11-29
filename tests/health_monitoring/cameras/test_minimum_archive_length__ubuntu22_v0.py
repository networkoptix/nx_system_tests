# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.health_monitoring.cameras.test_minimum_archive_length__ import _test_minimum_archive_length


class test_ubuntu22_v0(VMSTest):
    """Test minimum archive length.

    See: https://networkoptix.atlassian.net/browse/FT-505
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/58144
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/58145
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/58164
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/58165
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/81191
    """

    def _run(self, args, exit_stack):
        _test_minimum_archive_length(args.distrib_url, 'ubuntu22', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v0().main())
