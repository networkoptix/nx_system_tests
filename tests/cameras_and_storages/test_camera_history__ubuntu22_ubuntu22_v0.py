# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.test_camera_history__ import _test_camera_switching_should_be_represented_in_history


class test_ubuntu22_ubuntu22_v0(VMSTest):
    """Test camera switching should be represented in history.

    See: https://networkoptix.atlassian.net/browse/TEST-178
    See: https://networkoptix.atlassian.net/wiki/spaces/SD/pages/77234376/Camera+history+test
    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_camera_switching_should_be_represented_in_history(args.distrib_url, ('ubuntu22', 'ubuntu22'), 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_ubuntu22_v0().main())
