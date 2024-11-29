# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.event_rules.test_post_content_type_auto_detection__ import _test_post_content_type_auto_detection


class test_ubuntu22_v0(VMSTest):
    """Test post content type auto detection.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/15845
    """

    def _run(self, args, exit_stack):
        _test_post_content_type_auto_detection(args.distrib_url, 'ubuntu22', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v0().main())
