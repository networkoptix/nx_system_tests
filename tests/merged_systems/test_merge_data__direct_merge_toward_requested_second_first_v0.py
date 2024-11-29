# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.merged_systems.test_merge_data__ import _test_responses_are_equal


class test_direct_merge_toward_requested_second_first_v0(VMSTest):
    """Test responses are equal.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/6183
    """

    def _run(self, args, exit_stack):
        _test_responses_are_equal(args.distrib_url, 'direct-merge_toward_requested.yaml', 'second', 'first', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_direct_merge_toward_requested_second_first_v0().main())
