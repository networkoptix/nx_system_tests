# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.test_motion_type__ import _test_motion_type


class test_win11_v1_motion_type_digit(VMSTest):
    """Test motion type.

    Selection-Tag: no_testrail
    Selection-Tag: gitlab
    """

    def _run(self, args, exit_stack):
        _test_motion_type(args.distrib_url, 'win11', 'v1', False, exit_stack)


if __name__ == '__main__':
    exit(test_win11_v1_motion_type_digit().main())
