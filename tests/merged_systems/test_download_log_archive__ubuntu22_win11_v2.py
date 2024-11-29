# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.merged_systems.test_download_log_archive__ import _test_download_log_archive


class test_ubuntu22_win11_v2(VMSTest):
    """Test download log archive.

    Selection-Tag: no_testrail
    See: https://networkoptix.atlassian.net/browse/FT-1864
    Selection-Tag: gitlab
    """

    def _run(self, args, exit_stack):
        _test_download_log_archive(args.distrib_url, ('ubuntu22', 'win11'), 'v2', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_win11_v2().main())
