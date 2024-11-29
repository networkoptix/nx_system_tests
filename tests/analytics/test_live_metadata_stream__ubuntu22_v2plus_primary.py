# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.analytics.test_live_metadata_stream__ import _test_live_metadata_stream
from tests.base_test import VMSTest


class test_ubuntu22_v2plus_primary(VMSTest):
    """Test live metadata stream.

    Selection-Tag: gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/91596
    """

    def _run(self, args, exit_stack):
        _test_live_metadata_stream(args.distrib_url, 'ubuntu22', 'v2plus', 'primary', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v2plus_primary().main())
