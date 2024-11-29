# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.web_content.test_read_static_web_content_info__ import _test_read_static_web_content_info


class test_ubuntu22_v2(VMSTest):
    """Test read static web content info.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/107915
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/107885
    """

    def _run(self, args, exit_stack):
        _test_read_static_web_content_info(args.distrib_url, 'ubuntu22', 'v2', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v2().main())
