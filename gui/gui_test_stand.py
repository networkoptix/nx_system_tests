# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from collections.abc import Collection
from contextlib import AbstractContextManager
from contextlib import ExitStack
from contextlib import contextmanager
from ipaddress import IPv4Network
from ipaddress import ip_network
from pathlib import Path
from typing import Mapping

from cloud_api import CloudAccount
from gui.desktop_scenarios import DesktopClientStand
from gui.desktop_scenarios import DesktopMachinePool
from installation import InstallerSupplier
from installation import Mediaserver
from installation import VmsBenchmarkInstallation
from installation import WindowsClientInstallation
from installation import WindowsMobileClient
from installation import public_ip_check_addresses
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.provisioned_mediaservers import LdapMachinePool
from mediaserver_scenarios.provisioned_mediaservers import LdapServerUnit
from mediaserver_scenarios.provisioned_mediaservers import MediaserverUnit
from mediaserver_scenarios.provisioned_mediaservers import OneMediaserverStand
from os_access import current_host_address
from vm.networks import setup_flat_network
from vm.vm import VM

_logger = logging.getLogger(__name__)


class GuiTestStand:

    def __init__(self, installer_supplier: InstallerSupplier, run_dir: Path):
        self._run_dir = run_dir
        self._installer_supplier = installer_supplier
        self._vm_objects = {}

    def install_benchmark(self, os_access) -> VmsBenchmarkInstallation:
        installer = self._installer_supplier.upload_benchmark(os_access)
        installation = VmsBenchmarkInstallation(os_access)
        installation.install(installer)
        return installation

    @contextmanager
    def _create_mediaserver(self, server_key: str) -> AbstractContextManager[OneMediaserverStand]:
        if server_key not in ('VM', 'VM2'):
            raise ValueError(f"Unknown machine key: {server_key}")
        server_artifacts_dir = self._run_dir / f'mediaserver_{server_key}'
        server_artifacts_dir.mkdir()
        vm_pool = FTMachinePool(self._installer_supplier, server_artifacts_dir, 'v3')
        with vm_pool.one_mediaserver('ubuntu22') as mediaserver_stand:
            mediaserver_stand.os_access().networking.allow_multicast()  # For automatic discovery of the Mediaserver
            self._vm_objects[server_key] = mediaserver_stand.vm()
            yield mediaserver_stand

    @contextmanager
    def create_and_setup_only_client(
            self) -> AbstractContextManager[WindowsClientInstallation]:
        self._installer_supplier.distrib().latest_api_version(min_version='v3')
        vm_pool_client = DesktopMachinePool(self._run_dir / 'client', self._installer_supplier)
        with ExitStack() as stack:
            client_stand = stack.enter_context(vm_pool_client.client_stand())
            self._vm_objects['CLIENT'] = client_stand.vm()
            client_stand.set_screen_resolution(1600, 900, 32)
            stack.enter_context(client_stand.get_screen_recorder().record_video(self._run_dir))
            yield client_stand.installation()

    @contextmanager
    def prepared_mobile_client(self) -> AbstractContextManager[WindowsMobileClient]:
        self._installer_supplier.distrib().latest_api_version(min_version='v3')
        vm_pool = DesktopMachinePool(self._run_dir / 'mobile_client', self._installer_supplier)
        with ExitStack() as stack:
            mobile_client_stand = stack.enter_context(vm_pool.mobile_client_stand())
            stack.enter_context(mobile_client_stand.get_screen_recorder().record_video(self._run_dir))
            yield mobile_client_stand.installation()

    def get_testkit_port(self) -> int:
        port_mapping = self._vm_objects['CLIENT'].vm_control.port_map()
        return port_mapping['tcp'][7012]

    @contextmanager
    def setup_local_bundle_system(
            self) -> AbstractContextManager[tuple[Mediaserver, WindowsClientInstallation]]:
        self._installer_supplier.distrib().latest_api_version(min_version='v3')
        with ExitStack() as stack:
            vm_pool = DesktopMachinePool(self._run_dir / 'bundle', self._installer_supplier)
            stand = stack.enter_context(vm_pool.bundle_stand())
            self._vm_objects['CLIENT'] = stand.vm()
            stand.server_installation().start()
            stand.server_installation().api.setup_local_system()
            stand.set_screen_resolution(1600, 900, 32)
            stack.enter_context(stand.get_screen_recorder().record_video(self._run_dir))
            yield stand.server_installation(), stand.client_installation()

    @contextmanager
    def setup_uninitialized_local_bundle_system(
            self) -> AbstractContextManager[tuple[Mediaserver, WindowsClientInstallation]]:
        self._installer_supplier.distrib().latest_api_version(min_version='v3')
        with ExitStack() as stack:
            vm_pool = DesktopMachinePool(self._run_dir / 'bundle', self._installer_supplier)
            stand = stack.enter_context(vm_pool.bundle_stand())
            self._vm_objects['CLIENT'] = stand.vm()
            stand.server_installation().start()
            stand.set_screen_resolution(1600, 900, 32)
            stack.enter_context(stand.get_screen_recorder().record_video(self._run_dir))
            yield stand.server_installation(), stand.client_installation()

    @contextmanager
    def setup_server_client_for_cloud_tests(
            self,
            cloud_host: str,
            services_hosts: Collection[str],
            ) -> AbstractContextManager[tuple[Mediaserver, WindowsClientInstallation]]:
        self._installer_supplier.distrib().latest_api_version(min_version='v3')
        vm_pool_client = DesktopMachinePool(self._run_dir / 'client', self._installer_supplier)
        with ExitStack() as stack:
            client_stand = stack.enter_context(vm_pool_client.client_stand())
            self._vm_objects['CLIENT'] = client_stand.vm()
            server_stand = stack.enter_context(self._create_mediaserver('VM'))
            server_stand.os_access().cache_dns_in_etc_hosts([cloud_host, *public_ip_check_addresses, *services_hosts])
            server_stand.os_access().networking.allow_hosts([cloud_host, *public_ip_check_addresses, *services_hosts])
            server_stand.mediaserver().set_cloud_host(cloud_host)
            server_stand.mediaserver().start()
            server_stand.api().setup_local_system()
            server_stand.api().set_system_settings({'autoDiscoveryEnabled': 'False'})
            client_stand.os_access().cache_dns_in_etc_hosts([cloud_host, *public_ip_check_addresses, *services_hosts])
            client_stand.os_access().networking.allow_hosts([cloud_host, *public_ip_check_addresses, *services_hosts])
            client_stand.installation().set_ini('desktop_client.ini', {'cloudHost': cloud_host})
            client_stand.set_screen_resolution(1600, 900, 32)
            stack.enter_context(client_stand.get_screen_recorder().record_video(self._run_dir))
            yield server_stand.mediaserver(), client_stand.installation()

    @contextmanager
    def setup_server_client(
            self) -> AbstractContextManager[tuple[Mediaserver, WindowsClientInstallation]]:
        self._installer_supplier.distrib().latest_api_version(min_version='v3')
        vm_pool_client = DesktopMachinePool(self._run_dir / 'client', self._installer_supplier)
        with ExitStack() as stack:
            client_stand = stack.enter_context(vm_pool_client.client_stand())
            self._vm_objects['CLIENT'] = client_stand.vm()
            server_stand = stack.enter_context(self._create_mediaserver('VM'))
            server_stand.mediaserver().start()
            server_stand.api().setup_local_system()
            server_stand.api().set_system_settings({'autoDiscoveryEnabled': 'False'})
            client_stand.set_screen_resolution(1600, 900, 32)
            stack.enter_context(client_stand.get_screen_recorder().record_video(self._run_dir))
            yield server_stand.mediaserver(), client_stand.installation()

    @contextmanager
    def setup_server_client_with_analytics_plugins(
            self,
            plugins_names,
            ) -> AbstractContextManager[tuple[Mediaserver, WindowsClientInstallation]]:
        self._installer_supplier.distrib().latest_api_version(min_version='v3')
        vm_pool_client = DesktopMachinePool(self._run_dir / 'client', self._installer_supplier)
        with ExitStack() as stack:
            client_stand = stack.enter_context(vm_pool_client.client_stand())
            self._vm_objects['CLIENT'] = client_stand.vm()
            server_stand = stack.enter_context(self._create_mediaserver('VM'))
            server_stand.mediaserver().enable_optional_plugins(plugins_names)
            server_stand.mediaserver().enable_analytics_logs()
            server_stand.mediaserver().start()
            server_stand.api().setup_local_system()
            server_stand.api().set_system_settings({'autoDiscoveryEnabled': 'False'})
            client_stand.set_screen_resolution(1600, 900, 32)
            stack.enter_context(client_stand.get_screen_recorder().record_video(self._run_dir))
            yield server_stand.mediaserver(), client_stand.installation()

    @contextmanager
    def setup_one_server(self) -> AbstractContextManager[Mediaserver]:
        with self._create_mediaserver('VM') as server_stand:
            server_stand.mediaserver().start()
            server_stand.api().setup_local_system()
            server_stand.api().set_system_settings({'autoDiscoveryEnabled': 'False'})
            yield server_stand.mediaserver()

    @contextmanager
    def setup_two_servers_client(
            self,
            ) -> AbstractContextManager[tuple[Mediaserver, Mediaserver, WindowsClientInstallation]]:
        self._installer_supplier.distrib().latest_api_version(min_version='v3')
        vm_pool_client = DesktopMachinePool(self._run_dir / 'client', self._installer_supplier)
        with ExitStack() as stack:
            client_stand = stack.enter_context(vm_pool_client.client_stand())
            self._vm_objects['CLIENT'] = client_stand.vm()
            server_stand = stack.enter_context(self._create_mediaserver('VM'))
            server_stand2 = stack.enter_context(self._create_mediaserver('VM2'))
            server_stand.mediaserver().start()
            server_stand.api().setup_local_system()
            server_stand.api().set_system_settings({'autoDiscoveryEnabled': 'False'})
            server_stand2.mediaserver().start()
            server_stand2.api().setup_local_system()
            server_stand2.api().set_system_settings({'autoDiscoveryEnabled': 'False'})
            server_stand.api().rename_server('first_server')
            server_stand2.api().rename_server('second_server')
            setup_flat_network(tuple(self.get_vm_objects().values()), IPv4Network('10.254.254.0/28'))
            client_stand.set_screen_resolution(1600, 900, 32)
            stack.enter_context(client_stand.get_screen_recorder().record_video(self._run_dir))
            yield server_stand.mediaserver(), server_stand2.mediaserver(), client_stand.installation()

    @contextmanager
    def setup_local_server_cloud_server_client(
            self,
            cloud_host: str,
            cloud_user: CloudAccount,
            ) -> AbstractContextManager[tuple[Mediaserver, Mediaserver, WindowsClientInstallation]]:
        self._installer_supplier.distrib().latest_api_version(min_version='v3')
        vm_pool_client = DesktopMachinePool(self._run_dir / 'client', self._installer_supplier)
        with ExitStack() as stack:
            client_stand = stack.enter_context(vm_pool_client.client_stand())
            self._vm_objects['CLIENT'] = client_stand.vm()
            cloud_services_hosts = cloud_user.get_services_hosts()
            server_stand_local = stack.enter_context(self._create_mediaserver('VM'))
            server_stand_cloud = stack.enter_context(self._create_mediaserver('VM2'))
            server_stand_local.os_access().cache_dns_in_etc_hosts([cloud_host, *public_ip_check_addresses, *cloud_services_hosts])
            server_stand_local.os_access().networking.allow_hosts([cloud_host, *public_ip_check_addresses, *cloud_services_hosts])
            server_stand_local.mediaserver().set_cloud_host(cloud_host)
            server_stand_local.mediaserver().start()
            server_stand_local.api().setup_local_system()
            server_stand_local.api().set_system_settings({'autoDiscoveryEnabled': 'True'})

            server_stand_cloud.os_access().cache_dns_in_etc_hosts([cloud_host, *public_ip_check_addresses, *cloud_services_hosts])
            server_stand_cloud.os_access().networking.allow_hosts([cloud_host, *public_ip_check_addresses, *cloud_services_hosts])
            server_stand_cloud.mediaserver().set_cloud_host(cloud_host)
            server_stand_cloud.mediaserver().start()
            server_stand_cloud.api().setup_cloud_system(cloud_user, {
                'cameraSettingsOptimization': 'false',
                'autoDiscoveryEnabled': 'true',
                'statisticsAllowed': 'false',
                })

            server_stand_local.api().rename_server('local_server')
            server_stand_cloud.api().rename_server('cloud_server')
            setup_flat_network(tuple(self.get_vm_objects().values()), IPv4Network('10.254.254.0/28'))

            client_stand.os_access().cache_dns_in_etc_hosts([cloud_host, *public_ip_check_addresses, *cloud_services_hosts])
            client_stand.os_access().networking.allow_hosts([cloud_host, *public_ip_check_addresses, *cloud_services_hosts])
            client_stand.installation().set_ini('desktop_client.ini', {'cloudHost': cloud_host})
            client_stand.set_screen_resolution(1600, 900, 32)
            stack.enter_context(client_stand.get_screen_recorder().record_video(self._run_dir))
            yield server_stand_local.mediaserver(), server_stand_cloud.mediaserver(), client_stand.installation()

    @contextmanager
    def setup_server_client_ldap(
            self) -> AbstractContextManager[tuple[DesktopClientStand, MediaserverUnit, LdapServerUnit]]:
        self._installer_supplier.distrib().latest_api_version(min_version='v3')
        client_vm_pool = DesktopMachinePool(self._run_dir / 'client', self._installer_supplier)
        ldap_artifacts_dir = self._run_dir / 'ldap_server'
        ldap_artifacts_dir.mkdir()
        ldap_vm_pool = LdapMachinePool(ldap_artifacts_dir)
        with ExitStack() as stack:
            ldap_vm = stack.enter_context(ldap_vm_pool.ldap_vm('openldap'))
            server_stand = stack.enter_context(self._create_mediaserver('VM'))
            client_stand = stack.enter_context(client_vm_pool.client_stand())
            ldap_vm.ensure_started(ldap_artifacts_dir)
            [addresses, nics] = setup_flat_network(
                [client_stand.vm(), server_stand.vm(), ldap_vm],
                ip_network('10.254.254.0/28'),
                )
            [_, mediaserver_ip, ldap_ip] = addresses
            [_, mediaserver_nic, ldap_nic] = nics
            ldap_installation = stack.enter_context(ldap_vm_pool.ldap_server('openldap', ldap_vm))
            ldap_unit = LdapServerUnit(ldap_vm, ldap_installation, ldap_ip, ldap_nic)
            mediaserver_unit = MediaserverUnit(
                server_stand.vm(), server_stand.mediaserver(), mediaserver_ip, mediaserver_nic)
            server_stand.mediaserver().start()
            server_stand.api().setup_local_system()
            server_stand.api().set_system_settings({'autoDiscoveryEnabled': 'False'})
            client_stand.set_screen_resolution(1600, 900, 32)
            stack.enter_context(client_stand.get_screen_recorder().record_video(self._run_dir))
            yield client_stand, mediaserver_unit, ldap_unit

    @contextmanager
    def setup_server_ldap(
            self) -> AbstractContextManager[tuple[MediaserverUnit, LdapServerUnit]]:
        self._installer_supplier.distrib().latest_api_version(min_version='v3')
        ldap_artifacts_dir = self._run_dir / 'ldap_server'
        ldap_artifacts_dir.mkdir()
        ldap_vm_pool = LdapMachinePool(ldap_artifacts_dir)
        with ExitStack() as stack:
            ldap_vm = stack.enter_context(ldap_vm_pool.ldap_vm('openldap'))
            server_stand = stack.enter_context(self._create_mediaserver('VM'))
            ldap_vm.ensure_started(ldap_artifacts_dir)
            [addresses, nics] = setup_flat_network(
                [server_stand.vm(), ldap_vm],
                ip_network('10.254.254.0/28'),
                )
            [mediaserver_ip, ldap_ip] = addresses
            [mediaserver_nic, ldap_nic] = nics
            ldap_installation = stack.enter_context(ldap_vm_pool.ldap_server('openldap', ldap_vm))
            ldap_unit = LdapServerUnit(ldap_vm, ldap_installation, ldap_ip, ldap_nic)
            mediaserver_unit = MediaserverUnit(
                server_stand.vm(), server_stand.mediaserver(), mediaserver_ip, mediaserver_nic)
            server_stand.mediaserver().start()
            server_stand.api().setup_local_system()
            server_stand.api().set_system_settings({'autoDiscoveryEnabled': 'False'})
            yield mediaserver_unit, ldap_unit

    def get_address_and_port_of_server_from_bundle_for_client(self, server: Mediaserver) -> tuple[str, int]:
        """Get localhost address and port on which server is listening.

        Client and Server from a Bundle are located on the same machine.
        """
        return '127.0.0.1', server.port

    def get_address_and_port_of_server_on_another_machine_for_client(self, server: Mediaserver) -> tuple[str, int]:
        """Address and port for Client to connect to Server on another machine.

        In the current implementation, the connection goes through the host
        by the means of VirtualBox forwarding.

        TODO: Give address and port for direct connection.
        """
        return current_host_address(), server.os_access.get_port('tcp', server.port)

    def get_vm_objects(self) -> Mapping[str, VM]:
        return self._vm_objects


def expected_ip_for_audit_trail(server_os_access, client_os_access):
    # Deduce the address of the client machine as it's seen in the OS with
    # the mediaserver when the client initiates a connection.
    # I.e. the peer (foreign) address in the 5-tuple of such a connection.
    # Usually, tests know nothing about the machine.
    # But this case may be a legitimate exception.
    if server_os_access.address == '127.0.0.1':
        # Assuming this is a VirtualBox VM with the "NAT" NIC type:
        # connections initiated from outside are seen as from the gateway.
        expected_ip = server_os_access.source_address()
    else:
        # Assuming direct IP connectivity, e.g. an AWS EC2 VM.
        expected_ip = client_os_access.address
    return expected_ip
