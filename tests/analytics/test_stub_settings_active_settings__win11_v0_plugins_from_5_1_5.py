# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.analytics.test_stub_settings_active_settings__ import _test_stub_settings_active_settings
from tests.base_test import VMSTest


class test_win11_v0_plugins_from_5_1_5(VMSTest):
    """Test stub settings active settings.

    Selection-Tag: old_analytics_plugins
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/104991
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/104992
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/104993
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/105692
    """

    def _run(self, args, exit_stack):
        # VMS-52169: Active settings are not supported in REST API. Using legacy instead.
        _test_stub_settings_active_settings(args.distrib_url, 'win11', 'v0', exit_stack, '5.1.5')


if __name__ == '__main__':
    exit(test_win11_v0_plugins_from_5_1_5().main())
