# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.updates.basics.test_backup_of_previous_database_is_created__ import _test_backup_of_previous_database_is_created


class test_ubuntu24_v4plus(VMSTest):
    """Test backup of previous database is created.

    Selection-Tag: gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/47315
    """

    def _run(self, args, exit_stack):
        _test_backup_of_previous_database_is_created(args.distrib_url, 'ubuntu24', 'v4plus', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu24_v4plus().main())
