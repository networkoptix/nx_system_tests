# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.licences.test_keep_deactivated_license_without_internet__ import _test_keep_deactivated_license_without_internet


class test_win2019_v1(VMSTest):
    """Test keep deactivated license without internet.

    Selection-Tag: gitlab
    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_keep_deactivated_license_without_internet(args.distrib_url, 'win2019', 'v1', exit_stack)


if __name__ == '__main__':
    exit(test_win2019_v1().main())
