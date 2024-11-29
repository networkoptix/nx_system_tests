# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.web_content.test_upload_static_web_content__ import _test_upload_static_web_content


class test_ubuntu22_v2(VMSTest):
    """Test upload static web content.

    Selection-Tag: gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/107917
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/107920
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/107887
    """

    def _run(self, args, exit_stack):
        _test_upload_static_web_content(args.distrib_url, 'ubuntu22', 'v2', 'Summary written by FT', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v2().main())
