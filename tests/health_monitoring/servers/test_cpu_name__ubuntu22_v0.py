# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.health_monitoring.servers.test_cpu_name__ import _test_cpu_name


class test_ubuntu22_v0(VMSTest):
    """Test cpu name.

    See: https://networkoptix.atlassian.net/browse/FT-797
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57614
    """

    def _run(self, args, exit_stack):
        _test_cpu_name(args.distrib_url, 'ubuntu22', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v0().main())
