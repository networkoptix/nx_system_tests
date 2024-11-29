# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.test_extra_leading_frame__ import _test_extra_leading_frame


class test_ubuntu22_v0(VMSTest):
    """Test extra leading frame.

    Selection-Tag: no_testrail
    Selection-Tag: gitlab
    """

    def _run(self, args, exit_stack):
        _test_extra_leading_frame(args.distrib_url, 'ubuntu22', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v0().main())
