# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.merged_systems.test_resource_synchronization.test_resource_remove_update_conflict__ import _test_resource_remove_update_conflict


class test_direct_merge_toward_requested_v1(VMSTest):
    """Test resource remove update conflict.

    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_resource_remove_update_conflict(args.distrib_url, 'direct-merge_toward_requested.yaml', 'v1', exit_stack)


if __name__ == '__main__':
    exit(test_direct_merge_toward_requested_v1().main())
