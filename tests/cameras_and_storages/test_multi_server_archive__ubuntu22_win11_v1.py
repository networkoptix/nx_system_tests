# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.test_multi_server_archive__ import _test_merged_and_separated_archive


class test_ubuntu22_win11_v1(VMSTest):
    """Test merged and separated archive.

    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_merged_and_separated_archive(args.distrib_url, ('ubuntu22', 'win11'), 'v1', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_win11_v1().main())
