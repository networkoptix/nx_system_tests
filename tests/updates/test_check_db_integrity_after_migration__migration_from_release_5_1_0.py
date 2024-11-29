# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.updates.test_check_db_integrity_after_migration__ import _test_check_db_integrity_after_update


class test_migration_from_release_5_1_0(VMSTest):
    """Test migration from release 5 1 0.

    See: https://networkoptix.atlassian.net/browse/FT-2395
    Selection-Tag: gitlab
    """

    def _run(self, args, exit_stack):
        release_distrib_url = 'https://artifactory.us.nxteam.dev/artifactory/release-vms/default/5.1.0.37133/linux/'
        _test_check_db_integrity_after_update(release_distrib_url, args.distrib_url, exit_stack)


if __name__ == '__main__':
    exit(test_migration_from_release_5_1_0().main())
