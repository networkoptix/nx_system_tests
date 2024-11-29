# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.test_hls_beyond_recorded__ import _test_hls_output_with_duration_greater_than_recorded


class test_ubuntu22_v0(VMSTest):
    """Test hls output with duration greater than recorded.

    See: https://networkoptix.atlassian.net/browse/VMS-4180
    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_hls_output_with_duration_greater_than_recorded(args.distrib_url, 'ubuntu22', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v0().main())
