# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.cameras_and_storages.test_server_should_pick_archive_file_with_time_after_db_time__ import _test_server_should_pick_archive_file_with_time_after_db_time


class test_ubuntu22_v4plus(VMSTest):
    """Test server should pick archive file with time after db time.

    See: https://networkoptix.atlassian.net/browse/VMS-3911
    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_server_should_pick_archive_file_with_time_after_db_time(args.distrib_url, 'ubuntu22', 'v4plus', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_v4plus().main())
