# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.licences.test_license_activation_issues__ import _test_license_activation_issues


class test_ubuntu22_v1(VMSTest):
    """Test license activation issues.

    Selection-Tag: gitlab
    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_license_activation_issues(args.distrib_url, 'ubuntu22', 'v1', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v1().main())
