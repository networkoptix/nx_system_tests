# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.analytics.test_roi__ import _test_stub_roi_agent_settings
from tests.base_test import VMSTest


class test_win11_v2plus_plugins_from_5_1_5(VMSTest):
    """Test stub roi agent settings.

    Selection-Tag: old_analytics_plugins
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/58173
    """

    def _run(self, args, exit_stack):
        _test_stub_roi_agent_settings(args.distrib_url, 'win11', 'v2plus', exit_stack, '5.1.5')


if __name__ == '__main__':
    exit(test_win11_v2plus_plugins_from_5_1_5().main())
