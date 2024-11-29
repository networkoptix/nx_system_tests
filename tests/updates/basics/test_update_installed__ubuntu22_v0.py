# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.updates.basics.test_update_installed__ import _test_update_installed


class test_ubuntu22_v0(VMSTest):
    """Test update installed.

    Selection-Tag: gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57807
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57289
    """

    def _run(self, args, exit_stack):
        _test_update_installed(args.distrib_url, 'ubuntu22', 'v0', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v0().main())
