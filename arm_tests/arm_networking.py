# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import re
import time
from ipaddress import IPv4Address
from ipaddress import IPv4Interface
from ipaddress import ip_address
from subprocess import CalledProcessError

from os_access import Networking
from os_access import PingError
from os_access import Ssh

_iptables_rules = [
    'OUTPUT -o lo -j ACCEPT',
    'OUTPUT -d 10.0.0.0/22 -j ACCEPT',  # Office network
    'OUTPUT -d 10.0.8.0/24 -j ACCEPT',  # ARM network
    'OUTPUT -j REJECT',
    ]


class ArmNetworking(Networking):

    def __init__(self, ssh: Ssh):
        self._ssh = ssh

    def __repr__(self):
        return f'<ArmsNetworking on {self._ssh}>'

    def get_ip_addresses(self):
        out = self._ssh.run(['ip', 'address', 'show', 'scope', 'global']).stdout
        # Looking for ip4/prefix_length substrings
        matches = re.findall('inet (\\S+)', out.decode())
        result = []
        for ip_addr_str in matches:
            ip_addr = IPv4Interface(ip_addr_str)
            result.append(ip_addr)
        return result

    def _link_is_up(self, nic_id):
        raise NotImplementedError("Not implemented yet for ARM machines")

    def setup_static_ip(self, nic_id, *ip_list):
        raise NotImplementedError("Not implemented yet for ARM machines")

    def set_route(self, destination_ip_net, gateway_bound_nic_id, gateway_ip):
        raise NotImplementedError("Not implemented yet for ARM machines")

    def disable_internet(self):
        for rule in _iptables_rules:  # Mind order or get locked!
            # Don't add duplicates, although it's matter of perfectionism.
            outcome = self._ssh.run(['iptables', '-C', *rule], check=False)
            if outcome.returncode == 0:
                continue
            self._ssh.run(['iptables', '-A', *rule])
        global_ip = '8.8.8.8'
        try:
            self.ping(global_ip)
        except PingError:
            pass
        else:
            raise RuntimeError(f'Global {global_ip} IP is reachable after disabling internet')

    def allow_subnet(self, network):
        raise NotImplementedError("Not implemented yet for ARM machines")

    def _block_subnet(self, network):
        raise NotImplementedError("Not implemented yet for ARM machines")

    def _allow_ip_range(self, first_ip, last_ip):
        self._ssh.run([
            'iptables', '-I', 'OUTPUT',
            '-m', 'iprange', '--dst-range', f'{first_ip}-{last_ip}',
            '-j', 'ACCEPT',
            ])

    def _allow_host(self, ip_addr):
        self._ssh.run([
            'iptables', '-I', 'OUTPUT',
            '-d', ip_addr,
            '-j', 'ACCEPT',
            ])

    def _block_host(self, ip_addr):
        self._ssh.run([
            'iptables', '-D', 'OUTPUT',
            '-d', ip_addr,
            '-j', 'ACCEPT',
            ])

    def allow_destination(self, network, protocol, port):
        raise NotImplementedError("Not implemented yet for ARM machines")

    def block_destination(self, network, protocol, port):
        raise NotImplementedError("Not implemented yet for ARM machines")

    def setup_nat(self, nic_id):
        raise NotImplementedError("Not implemented yet for ARM machines")

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

    def _set_interface_state(self, nic_id, enabled):
        raise NotImplementedError("Not implemented yet for ARM machines")

    def get_interface_name(self, nic_id):
        raise NotImplementedError("Not implemented yet for ARM machines")

    def get_interface_stats(self, nic_id):
        raise NotImplementedError("Not implemented yet for ARM machines")

    def disable_outbound_non_unicast(self):
        raise NotImplementedError("Not implemented yet for ARM machines")

    def _get_default_gateway_address(self):
        default_route_output = self._ssh.run(['ip', 'route', 'show', '0.0.0.0/0']).stdout.decode()
        [_, _, gateway_address, *_] = default_route_output.split()
        return IPv4Address(gateway_address)
