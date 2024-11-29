# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.licences.test_disable_cameras_recording_on_license_problems__ import _test_disable_cameras_recording_on_license_problems


class test_win11_ubuntu22_v0_no_licenses(VMSTest):
    """Test disable cameras recording on license problems.

    Selection-Tag: gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57389
    """

    def _run(self, args, exit_stack):
        _test_disable_cameras_recording_on_license_problems(args.distrib_url, ('win11', 'ubuntu22', 'ubuntu22'), 'v0', 1, 0, 0, exit_stack)


if __name__ == '__main__':
    exit(test_win11_ubuntu22_v0_no_licenses().main())
