# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.ldap.test_ldap_settings_after_upgrade__ import _test_ldap_settings_after_upgrade


class test_with_5_0_0(VMSTest):
    """Test connection settings to LDAP are saved after update to current version.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/119090
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/122072
    Selection-Tag: gitlab
    Selection-Tag: ldap
    """

    def _run(self, args, exit_stack):
        release_distrib_url = 'https://artifactory.us.nxteam.dev/artifactory/release-vms/default/5.0.0.35745/linux/'
        _test_ldap_settings_after_upgrade(release_distrib_url, args.distrib_url, exit_stack)


if __name__ == '__main__':
    exit(test_with_5_0_0().main())
