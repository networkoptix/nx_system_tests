# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import sys
from contextlib import ExitStack
from ipaddress import ip_network

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import Mediaserver
from mediaserver_api import ExplicitMergeError
from mediaserver_api import LdapSearchBase
from mediaserver_scenarios.merging import merge_systems
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.provisioned_mediaservers import LdapMachinePool
from os_access.ldap.server_installation import LDAPServerInstallation
from runner.ft_test import run_ft_test
from tests.base_test import VMSTest
from vm.networks import setup_flat_network


class test_ubuntu22_openldap(VMSTest):
    """Test merge Servers that connected to different LDAP servers is forbidden.

    Selection-Tag: gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/122558
    """

    def _run(self, args, exit_stack):
        _test_merge_servers_forbidden(
            distrib_url=args.distrib_url,
            two_vm_types=('ubuntu22', 'ubuntu22'),
            ldap_type='openldap',
            exit_stack=exit_stack,
            )


def _test_merge_servers_forbidden(
        distrib_url: str,
        two_vm_types: tuple[str, str],
        ldap_type: str,
        exit_stack: ExitStack,
        ):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    api_version = 'v3plus'
    artifact_dir = get_run_dir()
    pool = FTMachinePool(installer_supplier, artifact_dir, api_version)
    ldap_pool = LdapMachinePool(artifact_dir)
    ldap1_vm = exit_stack.enter_context(ldap_pool.ldap_vm('openldap'))
    ldap2_vm = exit_stack.enter_context(ldap_pool.ldap_vm('openldap'))
    mediaserver1_stand = exit_stack.enter_context(pool.one_mediaserver(two_vm_types[0]))
    mediaserver2_stand = exit_stack.enter_context(pool.one_mediaserver(two_vm_types[1]))
    ldap1_vm.ensure_started(artifact_dir)
    ldap2_vm.ensure_started(artifact_dir)
    [addresses, _] = setup_flat_network(
        [ldap1_vm, ldap2_vm, mediaserver1_stand.vm(), mediaserver2_stand.vm()],
        ip_network('10.254.254.0/28'),
        )
    [ldap1_ip, ldap2_ip, *_] = addresses
    ldap1_installation = exit_stack.enter_context(ldap_pool.ldap_server(ldap_type, ldap1_vm))
    ldap2_installation = exit_stack.enter_context(ldap_pool.ldap_server(ldap_type, ldap2_vm))
    _prepare_mediaserver(mediaserver1_stand.mediaserver(), ldap1_installation, str(ldap1_ip))
    _prepare_mediaserver(mediaserver2_stand.mediaserver(), ldap2_installation, str(ldap2_ip))
    try:
        merge_systems(mediaserver1_stand.mediaserver(), mediaserver2_stand.mediaserver(), False)
    except ExplicitMergeError as exc:
        message_text = (
            "is currently connected to a LDAP server that differs from the LDAP server used in the current"
            )
        assert message_text in exc.error_string, (
            f"Expected {message_text!r} in the message text, but it is not found. Got message "
            f"{exc.error_string!r}"
            )
    else:
        raise RuntimeError("Merge succeeded while it must not")


def _prepare_mediaserver(mediaserver: Mediaserver, ldap_server: LDAPServerInstallation, ldap_address: str):
    mediaserver.start()
    mediaserver.api.setup_local_system()
    search_base = LdapSearchBase(ldap_server.users_ou(), '', 'users')
    mediaserver.api.set_ldap_settings(
        ldap_address, ldap_server.admin_dn(), ldap_server.password(), [search_base])
    mediaserver.api.sync_ldap_users()


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [
        test_ubuntu22_openldap(),
        ]))
