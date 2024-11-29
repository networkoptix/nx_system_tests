# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.analytics.test_analytics_event_from_sample_agent__ import _test_analytics_event_from_sample_agent
from tests.base_test import VMSTest


class test_win11_v0(VMSTest):
    """Test analytics event from sample agent.

    Selection-Tag: gitlab
    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_analytics_event_from_sample_agent(args.distrib_url, 'win11', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_win11_v0().main())
