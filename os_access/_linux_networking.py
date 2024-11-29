# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import functools
import logging
import re
import time
from ipaddress import IPv4Address
from ipaddress import IPv4Interface
from ipaddress import ip_address
from subprocess import CalledProcessError
from typing import Mapping

from os_access._networking import Networking
from os_access._networking import PingError
from os_access._sftp_path import SftpPath
from os_access._ssh_shell import Ssh
from vm.hypervisor import PciAddress
from vm.hypervisor import PciAddressPart

_logger = logging.getLogger(__name__)


def _extract_linux_version_info(release_file_content: str) -> Mapping[str, str]:
    version_info = {}
    for line in release_file_content.splitlines():
        if '=' not in line:
            continue
        [key, value] = line.split('=')
        version_info[key] = value.strip('"\'')
    return version_info


class LinuxNetworking(Networking):

    def __init__(self, ssh: Ssh):
        self._ssh = ssh

    def __repr__(self):
        return '<LinuxNetworking on {!r}>'.format(self._ssh)

    @functools.lru_cache()
    def _interfaces(self) -> Mapping[PciAddress, str]:
        interfaces = {}
        adapters_output = self._ssh.run(['ls', '-1', '/sys/class/net']).stdout
        # The loopback interface doesn't have a PCI-ID
        adapters = [a for a in adapters_output.decode().rstrip().splitlines() if a != 'lo']
        for adapter_name in adapters:
            adapter = '/sys/class/net/' + adapter_name
            try:
                device_output = self._ssh.run(['readlink', '-e', adapter + '/device']).stdout
            except CalledProcessError as e:
                if e.returncode != 1 or e.stdout:
                    raise
                _logger.debug("No device symlink: %s", adapter)
                continue
            device = device_output.decode().rstrip()
            if not device.startswith('/sys/devices'):
                raise RuntimeError(
                    "Device symlink target is outside /sys/devices: {} ({})"
                    .format(adapter, device))
            root_bus, *path = device[len('/sys/devices/'):].split('/')
            # PCI root bus is something like pci0000:00.
            if not root_bus.startswith('pci'):
                _logger.debug('Not PCI: %s (%s)', adapter, device)
                continue
            pci_domain = int(root_bus[3:7], base=16)
            if pci_domain != 0:
                raise NotImplementedError(
                    "Multiple PCI domains support is not implemented; "
                    "they could appear on multi-processor systems: {} ({})"
                    .format(adapter, device))
            pci_root_bus_number = int(root_bus[8:10], base=16)
            if pci_root_bus_number != 0:
                raise NotImplementedError(
                    "Network adapters are assumed to be on root bus 0; "
                    "specifying bus number is not implemented: {} ({})"
                    .format(adapter, device))
            hw_id = []
            # VirtIO devices has additional part in their sysfs path: virtioN.
            for hop in (path[:-1] if path[-1].startswith('virtio') else path):
                # Hop is a bridge or an actual adapter, if it's the last part.
                # It looks like 0000:00:0d.0 (domain:bus:device.function).
                # Bus number is assigned by OS according its own rules,
                # the real identifier is the sequence of device-function pairs.
                device_number = int(hop[8:10], base=16)
                function_number = int(hop[11:12], base=16)
                hw_id.append(PciAddressPart(device_number, function_number))
            _logger.debug("Interface %s: %s", adapter_name, hw_id)
            interfaces[PciAddress(*hw_id)] = adapter_name
        return interfaces

    def _systemd_reset_interface(self, interface: str):
        config_file = self._sftp_path(f"/etc/systemd/network/50-{interface}.network")
        config_file.unlink(missing_ok=True)
        self._ssh.run(['ip', 'addr', 'flush', 'dev', interface])

    def _link_is_up(self, nic_id):
        adapter_name = self.get_interface_name(nic_id)
        output = self._ssh.run(['ip', 'link', 'show', adapter_name])
        return 'state UP' in output.stdout.decode('ascii')

    def _sftp_path(self, path):
        return SftpPath(self._ssh, path)

    def setup_static_ip(self, nic_id, *ip_list):
        interface = self._interfaces()[nic_id]
        self._systemd_reset_interface(interface)
        self._systemd_assign_static_ip(interface, *ip_list)
        _logger.info("Machine %r has IP %s on %s (%s).", self._ssh, ip_list, interface, nic_id)

    def _systemd_assign_static_ip(self, interface: str, *ip_list: IPv4Interface):
        config_text = f"[Match]\nName={interface}\n\n[Network]\n"
        for ip in ip_list:
            config_text += f"Address={ip}\n"
            self._ssh.run(['ip', 'address', 'add', str(ip), 'dev', interface])
        config_file = self._sftp_path(f"/etc/systemd/network/50-{interface}.network")
        config_file.write_text(config_text)

    def get_ip_addresses(self):
        out = self._ssh.run(['ip', 'address', 'show', 'scope', 'global']).stdout
        # Looking for ip4/prefix_length substrings
        matches = re.findall('inet (\\S+)', out.decode())
        result = []
        for ip_addr_str in matches:
            ip_addr = IPv4Interface(ip_addr_str)
            result.append(ip_addr)
        return result

    def set_route(self, destination_ip_net, gateway_bound_nic_id, gateway_ip):
        interface = self._interfaces()[gateway_bound_nic_id]
        self._ssh.run([
            'ip', 'route',
            'replace', destination_ip_net,
            'dev', interface,
            'via', gateway_ip,
            'proto', 'static',
            ])

    def disable_internet(self):
        # Don't add duplicates, although it's matter of perfectionism.
        outcome = self._ssh.run('iptables -C OUTPUT -o lo -j ACCEPT', check=False)
        if outcome.returncode != 0:
            self._ssh.run('iptables -I OUTPUT -o lo -j ACCEPT')
        self._ssh.run('iptables -A OUTPUT -j REJECT')
        global_ip = '8.8.8.8'
        try:
            self.ping(global_ip)
        except PingError:
            pass
        else:
            raise RuntimeError(f'Global {global_ip} IP is reachable after disabling internet')

    def allow_subnet(self, network):
        self._ssh.run(f'iptables -I OUTPUT -d {network} -j ACCEPT')

    def _block_subnet(self, network):
        self._ssh.run(f'iptables -D OUTPUT -d {network} -j ACCEPT')

    def _allow_ip_range(self, first_ip, last_ip):
        self._ssh.run(f'iptables -I OUTPUT -m iprange --dst-range {first_ip}-{last_ip} -j ACCEPT')

    def _allow_host(self, ip_addr: IPv4Address):
        self._ssh.run(f'iptables -I OUTPUT -d {ip_addr} -j ACCEPT')

    def _block_host(self, ip_addr: IPv4Address):
        self._ssh.run(f'iptables -D OUTPUT -d {ip_addr} -j ACCEPT')

    def allow_destination(self, network, protocol, port):
        self._ssh.run([
            'iptables', '-I', 'OUTPUT',
            '-d', network,
            '-p', protocol,
            '--dport', str(port),
            '-j', 'ACCEPT',
            ])

    def block_destination(self, network, protocol, port):
        self._ssh.run([
            'iptables', '-I', 'OUTPUT',
            '-d', network,
            '-p', protocol,
            '--dport', str(port),
            '-j', 'REJECT',
            ])

    def setup_nat(self, outer_nic_id):
        """Connection can be initiated from inner_net_nodes only. Addresses are masqueraded."""
        self._ssh.run(['sysctl', 'net.ipv4.ip_forward=1'])
        self._ssh.run([
            'iptables', '-t', 'nat', '-A', 'POSTROUTING',
            '-o', self._interfaces()[outer_nic_id],
            '-j', 'MASQUERADE',
            ])

    def ping(self, ip: str, timeout_sec=30):
        ip = ip_address(ip)
        # There are some reasons why first ping can fail,
        # i.e. it times out when ARP process have to
        # resolve next-hop MAC-address. Three pings
        # are used for a better reliability.
        started_at = time.monotonic()
        ping = 'ping' if ip.version == 4 else 'ping6'
        while True:
            try:
                self._ssh.run([ping, '-c', 1, '-W', 2, str(ip)])
            except CalledProcessError as e:  # See man page.
                if e.returncode != 1:
                    raise
                if b'Destination Port Unreachable' in e.stdout:
                    raise PingError(f'Received ICMP Port unreachable. Stdout: {e.stdout}', ip)
                if time.monotonic() - started_at > timeout_sec:
                    raise PingError(f'Stdout: {e.stdout}', ip)
            else:
                break
            time.sleep(0.5)

    def _set_interface_state(self, nic_id, enabled: bool):
        interface = self._interfaces()[nic_id]
        state = 'up' if enabled else 'down'
        return self._ssh.run(['ip', 'link', 'set', 'dev', interface, state])

    def get_interface_name(self, nic_id):
        return self._interfaces()[nic_id]

    def get_interface_stats(self, nic_id):
        interface_name = self.get_interface_name(nic_id)
        result = self._ssh.run([
            'cat',
            f'/sys/class/net/{interface_name}/statistics/rx_bytes',
            f'/sys/class/net/{interface_name}/statistics/tx_bytes'])
        output = result.stdout
        rx_bytes, tx_bytes = output.decode('ascii').splitlines()
        return int(rx_bytes), int(tx_bytes)

    def disable_outbound_non_unicast(self):
        self._ssh.run(['iptables', '-A', 'OUTPUT', '-d', '224.0.0.0/3', '-j', 'DROP'])

    def _get_default_gateway_address(self):
        default_route_output = self._ssh.run(['ip', 'route', 'show', '0.0.0.0/0']).stdout.decode()
        [_, _, gateway_address, *_] = default_route_output.split()
        return IPv4Address(gateway_address)
