# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.health_monitoring.servers.test_codec_threads__ import _test_codec_threads


class test_win11_v0(VMSTest):
    """Test codec threads.

    See: https://networkoptix.atlassian.net/browse/FT-785
    See: https://networkoptix.atlassian.net/browse/FT-786
    See: https://networkoptix.atlassian.net/browse/FT-787
    See: https://networkoptix.atlassian.net/browse/FT-788
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57523
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57521
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57526
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57527
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57528
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57531
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57532
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57536
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57538
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57539
    """

    def _run(self, args, exit_stack):
        _test_codec_threads(args.distrib_url, 'win11', 'v0', 5, exit_stack)


if __name__ == '__main__':
    exit(test_win11_v0().main())
