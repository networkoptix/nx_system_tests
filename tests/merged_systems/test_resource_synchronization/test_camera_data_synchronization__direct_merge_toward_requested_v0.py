# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.merged_systems.test_resource_synchronization.test_camera_data_synchronization__ import _test_camera_data_synchronization


class test_direct_merge_toward_requested_v0(VMSTest):
    """Test camera data synchronization.

    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_camera_data_synchronization(args.distrib_url, 'direct-merge_toward_requested.yaml', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_direct_merge_toward_requested_v0().main())
