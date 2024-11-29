# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.merged_systems.test_resource_synchronization.test_mediaserver_data_synchronization__ import _test_mediaserver_data_synchronization


class test_direct_no_merge_v1(VMSTest):
    """Test mediaserver data synchronization.

    Selection-Tag: no_testrail
    Selection-Tag: gitlab
    """

    def _run(self, args, exit_stack):
        _test_mediaserver_data_synchronization(args.distrib_url, 'direct-no_merge.yaml', 'v1', exit_stack)


if __name__ == '__main__':
    exit(test_direct_no_merge_v1().main())