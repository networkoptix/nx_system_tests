# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.analytics.test_object_search__ import _test_object_search
from tests.base_test import VMSTest


class test_ubuntu22_v0_plugins_from_5_1_5(VMSTest):
    """Test object search.

    Selection-Tag: old_analytics_plugins
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/56684
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/91587
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/91647
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/91790
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/91623
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/56687
    """

    def _run(self, args, exit_stack):
        _test_object_search(args.distrib_url, 'ubuntu22', 'v0', exit_stack, '5.1.5')


if __name__ == '__main__':
    exit(test_ubuntu22_v0_plugins_from_5_1_5().main())
