# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import CloudTest
from tests.base_test import VMSTest
from tests.cloud.merge.test_cloud_merge_after_disconnect__ import _test_cloud_merge_after_disconnect


class test_ubuntu22_ubuntu22_v2(VMSTest, CloudTest):
    """Test cloud merge after disconnect.

    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_cloud_merge_after_disconnect(args.cloud_host, args.distrib_url, ('ubuntu22', 'ubuntu22'), 'v2', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_ubuntu22_v2().main())
