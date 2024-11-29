# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from ipaddress import IPv4Address
from ipaddress import IPv4Network
from ipaddress import ip_interface
from ipaddress import ip_network
from itertools import islice
from typing import Any
from typing import List
from typing import Mapping
from typing import Sequence
from typing import Tuple

from vm.vm import VM


def setup_flat_network(vms: Sequence[VM], network_ip: IPv4Network):
    [host_ips, host_nics] = _setup_subnet(vms, network_ip)
    for i, vm in enumerate(vms):
        remote_ips = host_ips[:i] + host_ips[i + 1:]
        for remote_ip in remote_ips:
            vm.os_access.networking.ping(str(remote_ip))
    return host_ips, host_nics


def setup_networks(
        machines: Mapping[str, VM],
        networks_tree,
        ) -> Mapping[str, Mapping[IPv4Network, Tuple[IPv4Address, Any]]]:

    assignments = {}

    def setup_top_level_net(name, tree):
        aliases = [*tree.keys()]  # Preserve order.
        subnet, addresses, nics = setup_net(name, aliases)
        for alias, nic_id in zip(aliases, nics):
            if tree[alias] is not None:
                setup_router(alias, nic_id, tree[alias], [subnet])

    def setup_inner_net(name, tree, router_alias, outer_nets: List[IPv4Network]):
        aliases = [router_alias, *tree.keys()]  # Preserve order.
        subnet, addresses, nics = setup_net(name, aliases, has_router=True)
        gw = addresses[0]  # Router is the gateway.
        for alias, nic in zip(aliases[1:], nics[1:]):
            for outer_net in outer_nets:
                machines[alias].os_access.networking.set_route(str(outer_net), nic, str(gw))
                machines[alias].os_access.networking.allow_subnet_unicast(outer_net)
            if tree[alias] is not None:
                setup_router(alias, nic, tree[alias], [*outer_nets, subnet])

    def setup_net(name, aliases, has_router=False):
        subnet = ip_network(name)
        hosts = [machines[alias] for alias in aliases]
        addresses, nics = _setup_subnet(hosts, subnet, has_router)
        for alias, address, nic in zip(aliases, addresses, nics):
            assignments.setdefault(alias, {})[subnet] = address, nic
        return subnet, addresses, nics

    def setup_router(alias, nic_id, networks_tree, outer_nets: List[IPv4Network]):
        machines[alias].os_access.networking.setup_nat(nic_id)
        for net_name, net_tree in networks_tree.items():
            setup_inner_net(net_name, net_tree, alias, outer_nets)

    for net_name, net_tree in networks_tree.items():
        setup_top_level_net(net_name, net_tree)

    for alias in assignments:
        # Some topologies don't assume all-to-all connectivity on IP level,
        # so only ping neighbor IP addresses in local subnets.
        for ip_address in _get_neighbor_addresses(assignments, alias):
            machines[alias].os_access.networking.ping(str(ip_address), timeout_sec=20)

    return assignments


def _get_neighbor_addresses(assignments, alias):
    result = []
    local_networks = assignments[alias].keys()
    for neighbor_alias, net in assignments.items():
        if neighbor_alias == alias:
            continue
        for remote_net, [ip_address, _] in net.items():
            if remote_net not in local_networks:
                continue
            result.append(ip_address)
    return result


def _setup_subnet(vms: Sequence[VM], network_ip: IPv4Network, router=False):
    offset = 0 if router else 1  # First address is reserved for a router.
    addresses = [*islice(network_ip.hosts(), offset, len(vms) + offset)]
    assert len(vms) == len(addresses)
    nics = make_ethernet_network(str(network_ip), vms)
    for vm, nic, address in zip(vms, nics, addresses):
        ip_settings = ip_interface((address, network_ip.prefixlen))
        vm.os_access.networking.setup_static_ip(nic, ip_settings)
        vm.os_access.networking.allow_subnet_unicast(network_ip)
    return addresses, nics


def make_ethernet_network(network_name: str, vms: Sequence[VM]):
    # Assume Ethernet network is up when all cables are connected and links on every VM are up.
    nic_ids = [vm.vm_control.plug_internal(network_name) for vm in vms]
    for vm, nic_id in zip(vms, nic_ids):
        vm.os_access.networking.enable_interface(nic_id)
    for vm, nic_id in zip(vms, nic_ids):
        vm.os_access.networking.wait_for_link(nic_id)
    return nic_ids


_logger = logging.getLogger(__name__)
