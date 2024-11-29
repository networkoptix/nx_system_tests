# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.analytics.test_stub_settings__ import _test_stub_settings
from tests.base_test import VMSTest


class test_win11_v2plus_plugins_from_5_1_5(VMSTest):
    """Test stub settings.

    Selection-Tag: gitlab
    Selection-Tag: no_testrail
    Selection-Tag: old_analytics_plugins
    """

    def _run(self, args, exit_stack):
        _test_stub_settings(args.distrib_url, 'win11', 'v2plus', exit_stack, '5.1.5')


if __name__ == '__main__':
    exit(test_win11_v2plus_plugins_from_5_1_5().main())
