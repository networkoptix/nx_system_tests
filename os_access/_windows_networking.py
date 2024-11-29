# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import collections
import functools
import logging
import time
from http.client import IncompleteRead
from http.client import RemoteDisconnected
from ipaddress import IPv4Address
from ipaddress import IPv4Interface
from ipaddress import ip_interface
from typing import Mapping
from typing import Optional

from os_access._networking import Networking
from os_access._networking import PingError
from os_access._powershell import run_powershell_script
from os_access._windows_performance_counters import PerformanceCounterEngine
from os_access._winrm import WinRM
from os_access._winrm import WinRMOperationTimeoutError
from os_access._winrm import WmiError
from os_access._winrm_shell import WinRMShell
from vm.hypervisor import PciAddress
from vm.hypervisor import PciAddressPart

_logger = logging.getLogger(__name__)

_Adapter = collections.namedtuple('_Adapter', [
    'caption',
    'name',
    'adapter_id',
    'adapter_ref',
    'adapter_conf_ref',
    'msft_adapter_ref',
    ])


class WindowsNetworking(Networking):
    _firewall_rule_name = 'NX-TestStandNetwork'
    _firewall_rule_display_name = 'NX Test Stand Network'

    def __init__(self, winrm: WinRM):
        self._winrm = winrm

    def __repr__(self):
        return '<WindowsNetworking on {}>'.format(self._winrm)

    @functools.lru_cache()
    def _interfaces(self) -> Mapping[PciAddress, _Adapter]:
        result = {}
        adapters = list(self._winrm.wsman_all('Win32_NetworkAdapter'))
        associations = list(self._winrm.wsman_all('Win32_NetworkAdapterSetting'))
        msft_adapters = list(self._winrm.wsman_all('wmi/Root/StandardCimV2/MSFT_NetAdapter'))
        for adapter_ref, adapter in adapters:
            caption = adapter['Caption']
            pnp_id = adapter['PNPDeviceID']
            # Sometime we can get the ethernet adapter with pnp_id equal to
            # None. Generally it's a virtual adapters. They don't used but
            # a None value causes the errors further in test setup.
            if pnp_id is None:
                _logger.info("The {} has no pnp_id".format(caption))
                continue
            # The most "correct" and precise way to match adapter and its
            # configurations is to find their association.
            for _, association in associations:
                if association['Element'] == adapter_ref:
                    adapter_conf_ref = association['Setting']
                    break
            else:
                raise RuntimeError("Cannot find adapter conf: {} ({})".format(caption, pnp_id))
            # See: https://docs.microsoft.com/en-us/windows-hardware/drivers/install/identifiers-for-pci-devices  # NOQA
            hardware_interface_type, _model, local_id = pnp_id.split('\\')
            if hardware_interface_type != 'PCI':
                _logger.debug('Not PCI: %s (%s)', caption, pnp_id)
                continue
            # Match adapter and msft_adapter via InterfaceIndex
            for ref, msft_adapter in msft_adapters:
                if adapter['InterfaceIndex'] == msft_adapter['InterfaceIndex']:
                    msft_adapter_ref = ref
                    name = msft_adapter['Name']
                    adapter_id = msft_adapter['InstanceID']
                    break
            else:
                raise RuntimeError(
                    "Cannot find msft adapter conf: {} ({})".format(caption, pnp_id))
            # The way how local id is constructed is not documented.
            # The reliable way to get bus, device and function is
            # exploring Win32_PnPEntity, its DEVPKEY_Device_Address property
            # via GetDeviceProperties() and its relation to Win32_Bus objects.
            # On Windows 10, it looks like 3&267A616A&0&88.
            _, _, bus_part, device_function_part = local_id.split('&')
            bus_number = int(bus_part, base=16)
            if bus_number not in {0, 1, 2}:
                raise NotImplementedError(
                    "Addressing PCI devices via bridges is not implemented; "
                    "the root bus must be number 0, 1 or 2: {} ({})"
                    .format(caption, pnp_id))
            device_number = int(device_function_part, base=16) >> 3
            function_number = int(device_function_part, base=16) & 0b111
            hw_id = PciAddress(PciAddressPart(device_number, function_number))
            _logger.debug("Interface %s: %s", caption, hw_id)
            result[hw_id] = _Adapter(
                caption, name, adapter_id, adapter_ref, adapter_conf_ref, msft_adapter_ref)
        return result

    def get_ip_addresses(self):
        adapters_conf = list(self._winrm.wsman_all('Win32_NetworkAdapterConfiguration'))
        result = []
        for _, adapter in adapters_conf:
            try:
                ip_addresses = adapter['IPAddress']
            except KeyError:
                continue
            subnet_masks = adapter['IPSubnet']
            if not isinstance(ip_addresses, list):
                ip_addresses = [ip_addresses]
            if not isinstance(subnet_masks, list):
                subnet_masks = [subnet_masks]
            for address, netmask in zip(ip_addresses, subnet_masks):
                ip_addr = ip_interface(f'{address}/{netmask}')
                if not isinstance(ip_addr, IPv4Interface):
                    _logger.debug("IP %s is not IPv4", ip_addr)
                    continue
                result.append(ip_addr)
        return result

    def _firewall_rule_exists(self, suffix):
        rules = list(
            self._winrm.wsman_select(
                'wmi/Root/StandardCimV2/MSFT_NetFirewallRule',
                {'InstanceID': self._firewall_rule_name + suffix}))
        return bool(rules)

    def _create_firewall_rule(self, action, remote_addresses, suffix, protocol=None, port=None):
        # No problem if there are multiple identical rules.
        name = self._firewall_rule_name + suffix
        display_name = self._firewall_rule_display_name + suffix
        action = {'Allow': 2, 'Block': 4}[action]
        properties_dict = {
            # See on numeric constants: https://msdn.microsoft.com/en-us/library/jj676843(v=vs.85).aspx
            'InstanceID': name,
            'ElementName': display_name,
            'Direction': 2,  # Outbound.
            'Action': action,
            'RuleGroup': self._firewall_rule_name,
            }
        try:
            ref = self._winrm.wsman_create(
                'wmi/Root/StandardCimV2/MSFT_NetFirewallRule', properties_dict)
        except WmiError as e:
            if e.code != WmiError.ALREADY_EXISTS:
                raise
            _logger.debug("Firewall rule already exists.")
        else:
            [[address_filter_ref, _]] = self._winrm.wsman_associated(
                'wmi/Root/StandardCimV2/MSFT_NetFirewallRule', ref.selectors,
                'MSFT_NetFirewallRuleFilterByAddress',
                'MSFT_NetAddressFilter')
            self._winrm.wsman_put(
                *address_filter_ref,
                {'RemoteAddress': remote_addresses})
            if protocol is not None:
                [[proto_port_filter_ref, _]] = self._winrm.wsman_associated(
                    'wmi/Root/StandardCimV2/MSFT_NetFirewallRule', ref.selectors,
                    'MSFT_NetFirewallRuleFilterByProtocolPort',
                    'MSFT_NetProtocolPortFilter')
                self._winrm.wsman_put(
                    *proto_port_filter_ref,
                    {'Protocol': protocol, 'RemotePort': None if port is None else str(port)})

    def _remove_firewall_rule(self, suffix):
        rules = list(self._winrm.wsman_select(
            'wmi/Root/StandardCimV2/MSFT_NetFirewallRule',
            {'InstanceID': self._firewall_rule_name + suffix}))
        if rules:
            [[rule_ref, _]] = rules
            self._winrm.wsman_delete(*rule_ref)

    def vm_default_firewall_rule_exists(self):
        return self._firewall_rule_exists('_vm_default')

    def remove_vm_default_firewall_rule(self):
        self._remove_firewall_rule('_vm_default')

    def _allow_outbound_by_default(self, allow):
        value = 0 if allow else 1  # "0 -> enable, 1 or any positive -> disable.
        for profile_name in {'Private', 'Domain', 'Public'}:
            self._winrm.wsman_put(
                'wmi/Root/StandardCimV2/MSFT_NetFirewallProfile',
                {'InstanceID': f'MSFT|FW|FirewallProfile|{profile_name}'},
                {'DefaultOutboundAction': value})

    def disable_internet(self):
        self._allow_outbound_by_default(False)

    def allow_subnet(self, network):
        self._create_firewall_rule('Allow', [network], f'_{network}')

    def _block_subnet(self, network):
        self._remove_firewall_rule(f'_{network}')

    def _allow_ip_range(self, first_ip, last_ip):
        range_str = f'{first_ip}-{last_ip}'
        self._create_firewall_rule('Allow', [range_str], f'_{range_str}')

    def _allow_host(self, ip_addr: IPv4Address):
        self._create_firewall_rule('Allow', [ip_addr], f'_{ip_addr}')

    def _block_host(self, ip_addr: IPv4Address):
        self._remove_firewall_rule(f'_{ip_addr}')

    def allow_destination(self, network, protocol, port):
        # Windows checks 'block' rules before 'allow' rules
        # See https://learn.microsoft.com/en-us/previous-versions/windows/it-pro/windows-server-2008-R2-and-2008/cc755191(v=ws.10)
        rule_suffix = f'_{network}_{protocol}_{port}'
        self._remove_firewall_rule(rule_suffix)
        self._create_firewall_rule('Allow', [network], rule_suffix, protocol, port)

    def block_destination(self, network, protocol, port):
        # See https://learn.microsoft.com/en-us/previous-versions/windows/it-pro/windows-server-2008-R2-and-2008/cc755191(v=ws.10)
        rule_suffix = f'_{network}_{protocol}_{port}'
        self._remove_firewall_rule(rule_suffix)
        self._create_firewall_rule('Block', [network], rule_suffix, protocol, port)

    def setup_static_ip(self, nic_id, *ip_list):
        adapter_conf = self._interfaces()[nic_id].adapter_conf_ref
        interface_index = self._winrm.wsman_get(*adapter_conf)['InterfaceIndex']
        ipv4_enabled = any(ip.version == 4 for ip in ip_list)
        ipv6_enabled = any(ip.version == 6 for ip in ip_list)
        self._set_adapter_ip_state(nic_id, ipv4_enabled=ipv4_enabled, ipv6_enabled=ipv6_enabled)
        # Deleting IP addresses for enabled IP versions.
        existing_ips = self._winrm.wsman_select(
            'wmi/Root/StandardCimV2/MSFT_NetIPAddress', {'InterfaceIndex': interface_index})
        for ip_ref, _ in existing_ips:
            self._winrm.wsman_delete(*ip_ref)
        for ip in ip_list:
            params = {
                'InterfaceIndex': str(interface_index),
                'IPAddress': str(ip.ip),
                'PrefixLength': str(ip.network.prefixlen)}
            try:
                self._winrm.wsman_invoke(
                    'wmi/Root/StandardCimV2/MSFT_NetIPAddress', {}, 'Create', params)
            except WmiError as e:
                if e.code != WmiError.INVALID_PARAMETER:
                    raise
                expected_message = (
                    'Inconsistent parameters PolicyStore PersistentStore and Dhcp Enabled')
                if expected_message not in e.message:
                    raise
                self._winrm.wsman_invoke(
                    'wmi/Root/StandardCimV2/MSFT_NetIPAddress', {}, 'Create', params)

    def set_route(self, destination_ip_net, gateway_bound_nic_id, gateway_ip):
        run_powershell_script(
            WinRMShell(self._winrm),
            # language=PowerShell
            '''
                $adapter = (gwmi Win32_NetworkAdapter -Filter "Caption='$caption'")
                $newRoute = New-NetRoute `
                    -DestinationPrefix:$destinationPrefix `
                    -InterfaceAlias:$adapter.NetConnectionID `
                    -NextHop:$nextHop
                ''',
            {
                'destinationPrefix': destination_ip_net,
                'nextHop': gateway_ip,
                'caption': self._interfaces()[gateway_bound_nic_id].caption,
                })

    def list_routes(self):
        result = run_powershell_script(
            WinRMShell(self._winrm),
            # language=PowerShell
            '''
                Get-NetRoute -PolicyStore:PersistentStore -AddressFamily:IPv4 -ErrorAction:SilentlyContinue |
                    select DestinationPrefix,InterfaceAlias,NextHop
                    ''',
            {})
        return result

    _ping_status_code_description = {
        '11002': 'Destination Net Unreachable',
        '11003': 'Destination Host Unreachable',
        '11010': 'Request Timed Out',
        }

    def ping(self, ip: str, timeout_sec=30):
        # There are some reasons why first ping can fail,
        # i.e. it times out when ARP process have to
        # resolve next-hop MAC-address.
        started_at = time.monotonic()
        while True:
            # According to https://learn.microsoft.com/en-us/previous-versions/windows/desktop/wmipicmp/win32-pingstatus
            # the default Timeout value is 1000 ms, but other sources tell it is 4000 ms.
            # According to real experience on Windows 10 it is 4000 ms. In rare cases Windows
            # responds only after 30 seconds timeout. To avoid this kind of situation, set Timeout explicitly.
            status = self._winrm.wsman_get('Win32_PingStatus', {'Address': ip, 'Timeout': '1000'})
            status_code = status['StatusCode']
            if status_code == '0':
                break
            if status_code == '11050':
                raise PingError("General Failure 11050; Windows Firewall may block access", status['Address'])
            if time.monotonic() - started_at > timeout_sec:
                if status_code in self._ping_status_code_description:
                    error = self._ping_status_code_description[status_code]
                else:
                    error = f"Ping status {status_code}; check Win32_PingStatus documentation"
                raise PingError(error, status['Address'])
            time.sleep(0.5)

    def _link_is_up(self, nic_id):
        # We need to ensure that both network adapter Win32_NetworkAdapter and
        # network interface MSFT_NetAdapter has connected. If MSFT_NetAdapter is down, setting
        # static IP address will fail, see
        # https://www.darrylvanderpeijl.com/inconsistent-parameters-policystore-persistentstore-and-dhcp-enabled/
        adapter = self._interfaces()[nic_id]
        try:
            win32_adapter = self._winrm.wsman_get(*adapter.adapter_ref)
            # See: https://docs.microsoft.com/en-us/windows/win32/cimwin32prov/win32-networkadapter
            msft_adapter = self._winrm.wsman_get(*adapter.msft_adapter_ref)
        except (RemoteDisconnected, IncompleteRead):
            # After reconfiguration the network (e.g., after setup_flat_network) current connection may be reset.
            time.sleep(0.5)
            win32_adapter = self._winrm.wsman_get(*adapter.adapter_ref)
            msft_adapter = self._winrm.wsman_get(*adapter.msft_adapter_ref)
        # See: https://docs.microsoft.com/en-us/previous-versions/windows/desktop/legacy/hh968170(v=vs.85)
        statuses = (
            win32_adapter['NetConnectionStatus'],
            msft_adapter['InterfaceOperationalStatus'],
            msft_adapter['MediaConnectState'],
            )
        _logger.debug(
            "Adapter %s statuses: "
            "NetConnectionStatus %s, InterfaceOperationalStatus %s, MediaConnectState %s",
            adapter.name, *statuses)
        return statuses == ('2', '1', '1')

    def setup_nat(self, outer_nic_id):
        raise NotImplementedError("Windows 10 cannot be set up as router out-of-the-box")

    def _set_interface_state(self, nic_id, enabled: bool):
        selectors = self._interfaces()[nic_id].adapter_ref.selectors
        interface = self._winrm.wsman_get('Win32_NetworkAdapter', selectors)
        # See: https://docs.microsoft.com/en-us/windows/desktop/cimwin32prov/win32-networkadapter
        if enabled and interface['ConfigManagerErrorCode'] == '22':  # Disabled.
            self._winrm.wsman_invoke(
                'Win32_NetworkAdapter', selectors, 'Enable', {})
        if not enabled and interface['ConfigManagerErrorCode'] == '0':  # Working properly.
            self._winrm.wsman_invoke(
                'Win32_NetworkAdapter', selectors, 'Disable', {})

    def _set_adapter_ip_state(self, nic_id, ipv4_enabled: bool, ipv6_enabled: bool):
        adapter_id = self._interfaces()[nic_id].adapter_id
        self._winrm.wsman_invoke(
            'wmi/Root/StandardCimV2/MSFT_NetAdapterBindingSettingData',
            {'InstanceID': f'{adapter_id}::ms_tcpip'},
            'Enable' if ipv4_enabled else 'Disable',
            {})
        self._winrm.wsman_invoke(
            'wmi/Root/StandardCimV2/MSFT_NetAdapterBindingSettingData',
            {'InstanceID': f'{adapter_id}::ms_tcpip6'},
            'Enable' if ipv6_enabled else 'Disable',
            {})

    def get_interface_name(self, nic_id):
        return self._interfaces()[nic_id].name

    def get_interface_stats(self, nic_id):
        adapter_name = self._winrm.wsman_get(*self._interfaces()[nic_id].adapter_ref)['Name']
        adapter_counter = _AdapterCounter(PerformanceCounterEngine(self._winrm), adapter_name)
        stats = adapter_counter.get_last_stats()
        rx_bytes = int(stats['BytesReceivedPersec'])
        tx_bytes = int(stats['BytesSentPersec'])
        return rx_bytes, tx_bytes

    def disable_outbound_non_unicast(self):
        self._create_firewall_rule('Block', ['224.0.0.0/3'], '_non_unicast')

    def _get_default_gateway_address(self):
        [[_, route]] = self._winrm.wsman_select(
            'wmi/Root/StandardCimV2/MSFT_NetRoute', {'DestinationPrefix': '0.0.0.0/0'})
        return IPv4Address(route['NextHop'])


# See: https://wutils.com/wmi/root/cimv2/win32_perfrawdata_tcpip_networkinterface
class _AdapterCounter:

    def __init__(self, counters_engine: PerformanceCounterEngine, adapter_name: str):
        # Win32_PerfRawData_Tcpip_NetworkInterface contains adapter name normalized by windows:
        # round brackets are replaced with square brackets; '#', '/', '\' are replaced with '_'
        adapter_name = adapter_name.translate(str.maketrans(r'()/\#', '[]___'))
        self._adapter_name = adapter_name
        self._counters_engine = counters_engine

    def get_last_stats(self) -> Mapping[str, Optional[str]]:
        attempt = 0
        while True:
            started_at = time.monotonic()
            try:
                # The first run of Win32_PerfRawData_Tcpip_NetworkInterface can take about 2 minutes.
                # The WinRM operational timeout is 120 seconds. Sometimes the run of
                # Win32_PerfRawData_Tcpip_NetworkInterface exceeds the operation timeout.
                [adapter_stats] = self._counters_engine.request_filtered(
                    'Win32_PerfRawData_Tcpip_NetworkInterface',
                    {'Name': str(self._adapter_name)})
            except WinRMOperationTimeoutError:
                if attempt >= 1:
                    raise
                attempt += 1
            else:
                return adapter_stats
            finally:
                _logger.debug(
                    'Win32_PerfRawData_Tcpip_NetworkInterface took %.2f seconds',
                    time.monotonic() - started_at)
