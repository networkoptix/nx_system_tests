# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.db_backup.test_backup_restore_on_merged_system__ import _test_backup_restore


class test_ubuntu22_ubuntu22_v0_current(VMSTest):
    """Test get streams.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1677
    See: https://networkoptix.atlassian.net/wiki/spaces/SD/pages/85690455/Mediaserver+database+test#Mediaserverdatabasetest-test_backup_restore
    TODO: Does it cover VMS-5969?
    See: https://networkoptix.atlassian.net/browse/VMS-5969
    See: https://networkoptix.atlassian.net/wiki/spaces/SD/pages/85690455/Mediaserver+database+test#Mediaserverdatabasetest-test_server_guids_changed
    See: 1cb73ab314e0214b657b285cfb9a59dd748e7be4
    """

    def _run(self, args, exit_stack):
        _test_backup_restore(args.distrib_url, ('ubuntu22', 'ubuntu22'), 'v0', 'current', exit_stack)


if __name__ == '__main__':
    exit(test_ubuntu22_ubuntu22_v0_current().main())
