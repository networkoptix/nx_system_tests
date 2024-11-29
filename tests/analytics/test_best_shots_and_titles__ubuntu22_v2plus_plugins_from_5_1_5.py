# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.analytics.test_best_shots_and_titles__ import _test_best_shots_and_titles
from tests.base_test import VMSTest


class test_ubuntu22_v2plus_plugins_from_5_1_5(VMSTest):
    """Test analytics track best shots and titles.

    Selection-Tag: gitlab
    Selection-Tag: old_analytics_plugins
    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_best_shots_and_titles(args.distrib_url, 'ubuntu22', 'v2plus', exit_stack, '5.1.5')


if __name__ == '__main__':
    exit(test_ubuntu22_v2plus_plugins_from_5_1_5().main())
