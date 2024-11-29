# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.analytics.test_analytics_object_detected_event__ import _test_analytics_object_detected_event
from tests.base_test import VMSTest


class test_ubuntu22_v2plus_plugins_from_5_1_5(VMSTest):
    """Test analytics object detected event.

    Selection-Tag: old_analytics_plugins
    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_analytics_object_detected_event(args.distrib_url, 'ubuntu22', 'v2plus', exit_stack, '5.1.5')


if __name__ == '__main__':
    exit(test_ubuntu22_v2plus_plugins_from_5_1_5().main())
