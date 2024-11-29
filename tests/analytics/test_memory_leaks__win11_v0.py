# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.analytics.test_memory_leaks__ import _test_memory_leaks_for_agents
from tests.base_test import VMSTest


class test_win11_v0(VMSTest):
    """Test memory leaks for agents.

    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_memory_leaks_for_agents(args.distrib_url, 'win11', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_win11_v0().main())
