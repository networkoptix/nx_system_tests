# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from collections.abc import Collection
from collections.abc import Mapping
from contextlib import AbstractContextManager
from contextlib import ExitStack
from contextlib import contextmanager
from ipaddress import IPv4Address
from ipaddress import IPv4Network
from ipaddress import ip_network
from pathlib import Path
from typing import Any
from typing import Literal
from typing import Optional

from ca import default_ca
from installation import InstallerSupplier
from installation import Mediaserver
from installation import find_mediaserver_installation
from installation import make_mediaserver_installation
from mediaserver_api import InsecureMediaserverApiV0
from mediaserver_api import MediaserverApi
from mediaserver_api import MediaserverApiV1
from mediaserver_api import MediaserverApiV2
from mediaserver_api import MediaserverApiV3
from mediaserver_api import MediaserverApiV4
from mediaserver_scenarios.merging import merge_systems
from mediaserver_scenarios.merging import setup_system
from os_access import OsAccess
from os_access.ldap.server_installation import ActiveDirectoryInstallation
from os_access.ldap.server_installation import LDAPServerInstallation
from os_access.ldap.server_installation import OpenLDAPInstallation
from vm.default_vm_pool import public_default_vm_pool
from vm.default_vm_pool import vm_types
from vm.hypervisor import PciAddress
from vm.hypervisor import Vm
from vm.networks import setup_flat_network
from vm.networks import setup_networks
from vm.nxwitness_snapshots.mediaserver_plugin import MediaserverPlugin
from vm.vm import VM

_logger = logging.getLogger(__name__)


class MediaserverUnit:

    def __init__(
            self,
            vm: VM,
            mediaserver: Mediaserver,
            subnet_ip: IPv4Address,
            subnet_nic: PciAddress,
            ):
        self._vm = vm
        self._mediaserver = mediaserver
        self._subnet_ip = subnet_ip
        self._subnet_nic = subnet_nic

    def api(self) -> MediaserverApi:
        return self._mediaserver.api

    def installation(self) -> Mediaserver:
        return self._mediaserver

    def os_access(self) -> OsAccess:
        return self._vm.os_access

    def vm(self) -> VM:
        return self._vm

    def subnet_ip(self) -> IPv4Address:
        return self._subnet_ip

    def subnet_nic(self) -> PciAddress:
        return self._subnet_nic


class LdapServerUnit:

    def __init__(
            self,
            vm: VM,
            ldap_server_installation: LDAPServerInstallation,
            subnet_ip: IPv4Address,
            subnet_nic: PciAddress,
            ):
        self._vm = vm
        self._ldap_server = ldap_server_installation
        self._subnet_ip = subnet_ip
        self._subnet_nic = subnet_nic

    def installation(self) -> LDAPServerInstallation:
        return self._ldap_server

    def subnet_ip(self) -> IPv4Address:
        return self._subnet_ip

    def disconnect_cable(self):
        # Assume that LDAP server is always reachable by a single link.
        self._vm.vm_control.disconnect_cable(self._subnet_nic)


LdapInstallationType = Literal['openldap', 'active_directory']


class TwoMediaserverStand:

    def __init__(self, first: MediaserverUnit, second: MediaserverUnit):
        self.first: MediaserverUnit = first
        self.second: MediaserverUnit = second

    def start(self):
        self.first.installation().start()
        self.second.installation().start()

    def setup_system(self, system_settings: Mapping[str, Any] | None = None):
        self.first.api().setup_local_system(system_settings=system_settings)
        self.second.api().setup_local_system(system_settings=system_settings)

    def merge(self):
        merge_systems(
            self.first.installation(),
            self.second.installation(),
            take_remote_settings=False,
            )


class OneMediaserverStand:

    def __init__(self, vm: 'VM', mediaserver: 'Mediaserver'):
        self._vm = vm
        self._mediaserver = mediaserver

    def api(self) -> MediaserverApi:
        return self._mediaserver.api

    def mediaserver(self) -> Mediaserver:
        return self._mediaserver

    def os_access(self) -> OsAccess:
        return self._vm.os_access

    def vm(self) -> VM:
        return self._vm

    def hardware(self) -> Vm:
        return self._vm.vm_control


class FTMachinePool:

    def __init__(
            self,
            installer_supplier: InstallerSupplier,
            artifact_dir: Path,
            api_version: str,
            ):
        self._installer_supplier: InstallerSupplier = installer_supplier
        self._artifact_dir: Path = artifact_dir
        self._vm_pool = public_default_vm_pool(self._artifact_dir)
        # After VMS-28118, Basic and Digest authentication types for admin are disabled by default.
        # This mark specifies whether to enable such disabled authentications.
        # MediaserverApiV0 uses Digest authentication. But starting with server version 5.0,
        # this authentication is disabled by default. Therefore, if the tests are using
        # MediaserverApiV0 on the latest server versions, this disabled authentication
        # should be manually enabled (using the "insecure" version of the API class).
        api_classes = {
            'v0': InsecureMediaserverApiV0,
            'v1': MediaserverApiV1,
            'v2': MediaserverApiV2,
            'v3': MediaserverApiV3,
            'v4': MediaserverApiV4,
            }
        if api_version in api_classes:
            installer_supplier.distrib().assert_api_support(api_version)
        elif api_version == 'v1plus':
            api_version = installer_supplier.distrib().latest_api_version(min_version='v1')
        elif api_version == 'v2plus':
            api_version = installer_supplier.distrib().latest_api_version(min_version='v2')
        elif api_version == 'v3plus':
            api_version = installer_supplier.distrib().latest_api_version(min_version='v3')
        elif api_version == 'v4plus':
            api_version = installer_supplier.distrib().latest_api_version(min_version='v4')
        else:
            raise RuntimeError(f'Unsupported API version: {api_version}')
        self._api_class = api_classes[api_version]
        self.two_vms_network_address: IPv4Network = ip_network('10.254.254.0/28')
        default_ca().add_to_env_vars()

    def clean_vm(self, vm_type: str) -> AbstractContextManager['VM']:
        return self._vm_pool.clean_vm(vm_types[vm_type])

    @contextmanager
    def two_mediaservers(
            self,
            two_vm_types,
            ) -> AbstractContextManager['TwoMediaserverStand']:
        for t in two_vm_types:
            self._installer_supplier.distrib().assert_os_support(t)
        first_vm_type, second_vm_type = two_vm_types
        with ExitStack() as stack:
            first_vm = stack.enter_context(self._vm_created(first_vm_type))
            second_vm = stack.enter_context(self._vm_created(second_vm_type))
            try:
                first_vm.ensure_started(self._artifact_dir)
                stack.enter_context(first_vm.os_access.traffic_capture_collector(self._artifact_dir))
                stack.enter_context(first_vm.os_access.prepared_one_shot_vm(self._artifact_dir))
                second_vm.ensure_started(self._artifact_dir)
                stack.enter_context(second_vm.os_access.traffic_capture_collector(self._artifact_dir))
                stack.enter_context(second_vm.os_access.prepared_one_shot_vm(self._artifact_dir))
                first_mediaserver = stack.enter_context(prepared_mediaserver_vm(first_vm, self._api_class, self._artifact_dir))
                second_mediaserver = stack.enter_context(prepared_mediaserver_vm(second_vm, self._api_class, self._artifact_dir))
                [[first_ip, second_ip], [first_nic, second_nic]] = setup_flat_network(
                    [first_vm, second_vm],
                    self.two_vms_network_address)
                yield TwoMediaserverStand(
                    MediaserverUnit(first_vm, first_mediaserver, first_ip, first_nic),
                    MediaserverUnit(second_vm, second_mediaserver, second_ip, second_nic),
                    )
            except Exception:
                logging.exception("An exception happened in two_mediaservers():")
                prefix = first_vm.os_access.netloc().replace(':', '-')
                first_vm.vm_control.take_screenshot(
                    self._artifact_dir / f'{prefix}-mediaserver_vm_exception.png')
                prefix = second_vm.os_access.netloc().replace(':', '-')
                second_vm.vm_control.take_screenshot(
                    self._artifact_dir / f'{prefix}-mediaserver_vm_exception.png')
                raise
            finally:
                first_vm.vm_control.copy_logs(self._artifact_dir)
                second_vm.vm_control.copy_logs(self._artifact_dir)

    @contextmanager
    def one_mediaserver(
            self,
            one_vm_type,
            ) -> AbstractContextManager['OneMediaserverStand']:
        self._installer_supplier.distrib().assert_os_support(one_vm_type)
        with ExitStack() as stack:
            one_vm = stack.enter_context(self._vm_created(one_vm_type))
            try:
                one_vm.ensure_started(self._artifact_dir)
                stack.enter_context(one_vm.os_access.traffic_capture_collector(self._artifact_dir))
                stack.enter_context(one_vm.os_access.prepared_one_shot_vm(self._artifact_dir))
                mediaserver = stack.enter_context(prepared_mediaserver_vm(one_vm, self._api_class, self._artifact_dir))
                yield OneMediaserverStand(one_vm, mediaserver)
            except Exception:
                logging.exception("An exception happened in one_mediaserver():")
                prefix = one_vm.os_access.netloc().replace(':', '-')
                one_vm.vm_control.take_screenshot(
                    self._artifact_dir / f'{prefix}-mediaserver_vm_exception.png')
                raise
            finally:
                one_vm.vm_control.copy_logs(self._artifact_dir)

    @contextmanager
    def mediaserver_allocation(self, os_access: OsAccess) -> AbstractContextManager[Mediaserver]:
        with ExitStack() as exit_stack:
            mediaserver = make_mediaserver_installation(os_access, self._installer_supplier.distrib().customization())
            exit_stack.callback(mediaserver.collect_artifacts, self._artifact_dir)
            installer = self._installer_supplier.upload_server_installer(os_access)
            host_addresses = os_access.networking.get_internal_addresses()
            mediaserver.setup(installer)
            mediaserver.init_key_pair(default_ca().generate_key_and_cert(os_access.address, *host_addresses))
            mediaserver.init_api(self._api_class(mediaserver.base_url()))
            # Try stopping mediaserver afterward to check whether it won't hang. This can be
            # disabled to allow playing with working mediaserver after the tests end.
            exit_stack.callback(mediaserver.stop, already_stopped_ok=True)
            exit_stack.callback(mediaserver.take_backtrace, 'after_test')
            exit_stack.callback(mediaserver.check_for_error_logs)
            # Examine before mediaserver is stopped: examination requires mediaserver be running.
            exit_stack.callback(mediaserver.examine)
            exit_stack.callback(mediaserver.output_metrics)
            yield mediaserver

    @contextmanager
    def vm_and_mediaserver_vm_network(
            self,
            two_vm_types,
            ):
        clean_vm_os, mediaserver_os = two_vm_types
        self._installer_supplier.distrib().assert_os_support(mediaserver_os)
        with ExitStack() as stack:
            clean_vm_ = stack.enter_context(self._vm_pool.clean_vm(vm_types[clean_vm_os]))
            mediaserver_vm = stack.enter_context(self._vm_created(mediaserver_os))
            try:
                clean_vm_.ensure_started(self._artifact_dir)
                mediaserver_vm.ensure_started(self._artifact_dir)
                stack.enter_context(clean_vm_.os_access.traffic_capture_collector(self._artifact_dir))
                stack.enter_context(mediaserver_vm.os_access.traffic_capture_collector(self._artifact_dir))
                stack.enter_context(clean_vm_.os_access.prepared_one_shot_vm(self._artifact_dir))
                stack.enter_context(mediaserver_vm.os_access.prepared_one_shot_vm(self._artifact_dir))
                mediaserver = stack.enter_context(prepared_mediaserver_vm(mediaserver_vm, self._api_class, self._artifact_dir))
                interfaces = setup_flat_network([clean_vm_, mediaserver_vm], self.two_vms_network_address)
                [[clean_vm_ip, mediaserver_ip], [clean_vm_nic, mediaserver_nic]] = interfaces
                unit = MediaserverUnit(mediaserver_vm, mediaserver, mediaserver_ip, mediaserver_nic)
                yield (clean_vm_ip, clean_vm_nic, clean_vm_), unit
            except Exception:
                logging.exception("An exception happened in vm_and_mediaserver_vm_network():")
                prefix = clean_vm_.os_access.netloc().replace(':', '-')
                clean_vm_.vm_control.take_screenshot(
                    self._artifact_dir / f'{prefix}-clean_vm_exception.png')
                prefix = mediaserver_vm.os_access.netloc().replace(':', '-')
                mediaserver_vm.vm_control.take_screenshot(
                    self._artifact_dir / f'{prefix}-mediaserver_vm_exception.png')
                raise
            finally:
                clean_vm_.vm_control.copy_logs(self._artifact_dir)
                mediaserver_vm.vm_control.copy_logs(self._artifact_dir)

    @contextmanager
    def three_mediaservers(
            self,
            system_settings: Mapping[str, str],
            ) -> AbstractContextManager[tuple[Mediaserver, Mediaserver, Mediaserver]]:
        layout = {
            'machines': [
                {'alias': 'one', 'type': 'ubuntu18'},
                {'alias': 'two', 'type': 'ubuntu18'},
                {'alias': 'three', 'type': 'ubuntu18'},
                ],
            'networks': {
                '10.254.0.0/28': {
                    'one': None,
                    'two': None,
                    'three': None,
                    },
                },
            'mergers': [],
            }
        with self.system(layout, system_settings) as [mediaservers, _machines, _assignments]:
            yield mediaservers['one'], mediaservers['two'], mediaservers['three']

    @contextmanager
    def system(
            self,
            layout,
            system_settings: Optional[Mapping[str, Any]] = None,
            ):
        for machine_config in layout['machines']:
            self._installer_supplier.distrib().assert_os_support(machine_config['type'])
        generic_machine_aliases = []
        mediaserver_machine_aliases = []
        for conf in layout['machines']:
            alias = conf['alias']
            if 'router' in alias or 'camera' in alias:
                generic_machine_aliases.append(alias)
            else:
                mediaserver_machine_aliases.append(alias)
        with ExitStack() as exit_stack:
            machines = {}
            for machine_config in layout['machines']:
                alias = machine_config['alias']
                if alias in generic_machine_aliases:
                    machines[alias] = exit_stack.enter_context(
                        self._vm_pool.clean_vm(vm_types[machine_config['type']]))
                else:
                    machines[alias] = exit_stack.enter_context(self._vm_created(machine_config['type']))
            for vm in machines.values():
                exit_stack.callback(vm.vm_control.copy_logs, self._artifact_dir)
                vm.ensure_started(artifacts_dir=self._artifact_dir)
                exit_stack.enter_context(vm.os_access.traffic_capture_collector(self._artifact_dir))
                exit_stack.enter_context(vm.os_access.prepared_one_shot_vm(self._artifact_dir))
            assignments = setup_networks(machines, layout['networks'])
            mediaservers = {}
            for alias in mediaserver_machine_aliases:
                vm = machines[alias]
                mediaserver = exit_stack.enter_context(prepared_mediaserver_vm(vm, self._api_class, self._artifact_dir))
                mediaservers[alias] = mediaserver
            for alias in mediaserver_machine_aliases:
                mediaservers[alias].start()
                mediaservers[alias].api.setup_local_system(system_settings)
            setup_system(mediaservers, layout['mergers'])
            yield mediaservers, machines, assignments

    def _vm_created(self, os_name: str):
        mediaserver_plugin = MediaserverPlugin(self._installer_supplier)
        return self._vm_pool.vm_created(mediaserver_plugin, vm_types[os_name])

    @contextmanager
    def ldap_vm_and_mediaservers_vm_network(
            self,
            mediaservers_vm_os: Collection[str],
            ldap_type: LdapInstallationType,
            ) -> AbstractContextManager[LdapServerUnit, MediaserverUnit, ...]:
        for one_vm_os in mediaservers_vm_os:
            self._installer_supplier.distrib().assert_os_support(one_vm_os)
        ldap_pool = LdapMachinePool(self._artifact_dir)
        with ExitStack() as stack:
            ldap_vm = stack.enter_context(ldap_pool.ldap_vm(ldap_type))
            mediaserver_stands = []
            for one_mediaserver_type in mediaservers_vm_os:
                mediaserver_stands.append(stack.enter_context(self.one_mediaserver(one_mediaserver_type)))
            mediaservers_vm = [stand.vm() for stand in mediaserver_stands]
            ldap_vm.ensure_started(self._artifact_dir)
            [addresses, nics] = setup_flat_network(
                [ldap_vm, *mediaservers_vm], self.two_vms_network_address)
            [ldap_server_ip, *mediaservers_ip] = addresses
            [ldap_server_nic, *mediaservers_nic] = nics
            ldap_installation = stack.enter_context(ldap_pool.ldap_server(ldap_type, ldap_vm))
            ldap_server_unit = LdapServerUnit(
                ldap_vm, ldap_installation, ldap_server_ip, ldap_server_nic)
            mediaservers = [stand.mediaserver() for stand in mediaserver_stands]
            mediaserver_units = []
            for vm, mediaserver, ip, nic in zip(
                    mediaservers_vm, mediaservers, mediaservers_ip, mediaservers_nic):
                mediaserver_units.append(MediaserverUnit(vm, mediaserver, ip, nic))
            yield ldap_server_unit, *mediaserver_units


class LdapMachinePool:

    _ldap_installation_types = {
        'openldap': OpenLDAPInstallation,
        'active_directory': ActiveDirectoryInstallation,
        }

    def __init__(self, artifact_dir: Path):
        self._artifact_dir = artifact_dir
        self._vm_pool = public_default_vm_pool(self._artifact_dir)

    @contextmanager
    def ldap_vm(self, ldap_type: LdapInstallationType) -> AbstractContextManager[VM]:
        if ldap_type not in self._ldap_installation_types:
            raise RuntimeError(f"{self}: unsupported LDAP server type: {ldap_type!s}")
        try:
            with self._vm_pool.clean_vm(vm_types[ldap_type]) as vm:
                yield vm
        except Exception:
            vm.vm_control.take_screenshot(
                self._artifact_dir / f'{vm.vm_control.name}-ldap_server_vm_exception.png')
            raise
        finally:
            vm.vm_control.copy_logs(self._artifact_dir)

    @contextmanager
    def ldap_server(
            self,
            ldap_type: LdapInstallationType,
            vm: VM,
            ) -> AbstractContextManager[LDAPServerInstallation]:
        try:
            ldap_class = self._ldap_installation_types[ldap_type]
        except KeyError:
            raise RuntimeError(f"{self}: unsupported LDAP server type: {ldap_type!s}")
        with ExitStack() as stack:
            stack.enter_context(vm.os_access.traffic_capture_collector(self._artifact_dir))
            stack.enter_context(vm.os_access.prepared_one_shot_vm(self._artifact_dir))
            ldap_server = ldap_class(vm.os_access)
            ldap_server.wait_until_ready()
            yield ldap_server


@contextmanager
def prepared_mediaserver_vm(
        vm: VM,
        api_class: type[MediaserverApi],
        artifacts_dir: Path,
        ) -> AbstractContextManager[Mediaserver]:
    with ExitStack() as exit_stack:
        mediaserver = find_mediaserver_installation(vm.os_access)
        mediaserver.stop(already_stopped_ok=True)
        mediaserver.update_ini('vms_server_plugins', {'disabledNxPlugins': 'nx_analytics_plugin'})
        exit_stack.callback(mediaserver.collect_artifacts, artifacts_dir)
        exit_stack.callback(mediaserver.check_for_error_logs)
        exit_stack.callback(mediaserver.stop, already_stopped_ok=True)
        mediaserver.init_key_pair(default_ca().generate_key_and_cert(vm.os_access.address))
        mediaserver.init_api(api_class(mediaserver.base_url()))
        exit_stack.callback(mediaserver.examine)
        exit_stack.callback(mediaserver.output_metrics)
        mediaserver.remove_data_from_previous_runs()
        mediaserver.enable_saving_console_output()
        try:
            yield mediaserver
        except Exception:
            mediaserver.take_backtrace('after_test')
            raise
