# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.merged_systems.test_resource_synchronization.test_user_data_synchronization__ import _test_user_data_synchronization


class test_direct_merge_toward_requested_v2(VMSTest):
    """Test user data synchronization.

    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_user_data_synchronization(args.distrib_url, 'direct-merge_toward_requested.yaml', 'v2', exit_stack)


if __name__ == '__main__':
    exit(test_direct_merge_toward_requested_v2().main())
