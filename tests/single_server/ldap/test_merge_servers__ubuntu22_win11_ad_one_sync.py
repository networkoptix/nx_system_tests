# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from tests.base_test import VMSTest
from tests.single_server.ldap.test_merge_servers__ import _test_merge_servers


class test_ubuntu22_win11_ad_one_sync(VMSTest):
    """Test merge servers, one of which is connected to an LDAP server.

    Selection-Tag: gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/122556
    """

    def _run(self, args, exit_stack):
        _test_merge_servers(
            distrib_url=args.distrib_url,
            first_os_name='ubuntu22',
            first_connected_to_ldap=True,
            second_os_name='win11',
            second_connected_to_ldap=False,
            master_is_first=True,
            ldap_type='active_directory',
            exit_stack=exit_stack,
            )


if __name__ == '__main__':
    exit(test_ubuntu22_win11_ad_one_sync().main())
