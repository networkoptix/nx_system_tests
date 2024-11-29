# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.analytics.test_roi__ import _test_stub_roi_agent_settings
from tests.base_test import VMSTest


class test_ubuntu22_v2plus(VMSTest):
    """Test stub roi agent settings.

    Selection-Tag: gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/58173
    """

    def _run(self, args, exit_stack):
        _test_stub_roi_agent_settings(args.distrib_url, 'ubuntu22', 'v2plus', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v2plus().main())
