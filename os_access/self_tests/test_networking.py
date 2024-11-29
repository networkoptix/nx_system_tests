# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import re
from ipaddress import IPv4Interface
from ipaddress import IPv6Interface
from ipaddress import ip_interface
from typing import Collection
from typing import Union

from directories import get_run_dir
from os_access import PingError
from os_access import Ssh
from tests.infra import assert_raises
from vm.default_vm_pool import public_default_vm_pool
from vm.default_vm_pool import vm_types
from vm.networks import make_ethernet_network


def _get_all_addresses(ssh: Ssh, interface_name: str) -> Collection[Union[IPv4Interface, IPv6Interface]]:
    # os_access.networking.get_ip_addresses()
    # returns only IPv4 addresses, here we return all addresses.
    ip_address_re = re.compile(r'inet6?\s+(?P<ip>.+?)\s+')
    ip_process = ssh.run(['ip', 'address', 'show', 'scope', 'global', 'dev', interface_name])
    ip_stdout = ip_process.stdout.decode('ascii')
    addresses = re.finditer(ip_address_re, ip_stdout)
    result = []
    for match in addresses:
        result.append(ip_interface(match.group('ip')))
    return result


def _get_manually_set_ip_addresses(interface_name, os_access):
    ip_addresses = _get_all_addresses(os_access.shell, interface_name)
    manually_set_ip_addresses = [x for x in ip_addresses if not x.ip.is_link_local]
    return manually_set_ip_addresses


def test_interfaces_ubuntu18(exit_stack):
    _test_interfaces('ubuntu18', exit_stack)


def test_interfaces_win11(exit_stack):
    _test_interfaces('win11', exit_stack)


def _test_interfaces(one_vm_type, exit_stack):
    artifacts_dir = get_run_dir()
    vm_pool = public_default_vm_pool(artifacts_dir)
    one_vm = exit_stack.enter_context(vm_pool.clean_vm(vm_types[one_vm_type]))
    one_vm.ensure_started(artifacts_dir)
    exit_stack.enter_context(one_vm.os_access.prepared_one_shot_vm(artifacts_dir))
    exit_stack.enter_context(one_vm.os_access.traffic_capture_collector(artifacts_dir))
    assert one_vm.os_access.networking._interfaces()
    assert all(one_vm.os_access.networking._interfaces().values())


def test_ping_localhost_ubuntu18(exit_stack):
    _test_ping_localhost('ubuntu18', exit_stack)


def test_ping_localhost_win11(exit_stack):
    _test_ping_localhost('win11', exit_stack)


def _test_ping_localhost(one_vm_type, exit_stack):
    artifacts_dir = get_run_dir()
    vm_pool = public_default_vm_pool(artifacts_dir)
    one_vm = exit_stack.enter_context(vm_pool.clean_vm(vm_types[one_vm_type]))
    one_vm.ensure_started(artifacts_dir)
    exit_stack.enter_context(one_vm.os_access.prepared_one_shot_vm(artifacts_dir))
    exit_stack.enter_context(one_vm.os_access.traffic_capture_collector(artifacts_dir))
    one_vm.os_access.networking.ping('127.0.0.1')


def test_ping_invalid_address_ubuntu18(exit_stack):
    _test_ping_invalid_address('ubuntu18', exit_stack)


def test_ping_invalid_address_win11(exit_stack):
    _test_ping_invalid_address('win11', exit_stack)


def _test_ping_invalid_address(one_vm_type, exit_stack):
    artifacts_dir = get_run_dir()
    vm_pool = public_default_vm_pool(artifacts_dir)
    one_vm = exit_stack.enter_context(vm_pool.clean_vm(vm_types[one_vm_type]))
    one_vm.ensure_started(artifacts_dir)
    exit_stack.enter_context(one_vm.os_access.prepared_one_shot_vm(artifacts_dir))
    exit_stack.enter_context(one_vm.os_access.traffic_capture_collector(artifacts_dir))
    with assert_raises(PingError):
        one_vm.os_access.networking.ping('192.0.2.1')


def test_flush_addresses_ubuntu18(exit_stack):
    _test_flush_addresses('ubuntu18', exit_stack)


def _test_flush_addresses(one_vm_type, exit_stack):
    artifacts_dir = get_run_dir()
    vm_pool = public_default_vm_pool(artifacts_dir)
    one_vm = exit_stack.enter_context(vm_pool.clean_vm(vm_types[one_vm_type]))
    one_vm.ensure_started(artifacts_dir)
    exit_stack.enter_context(one_vm.os_access.prepared_one_shot_vm(artifacts_dir))
    exit_stack.enter_context(one_vm.os_access.traffic_capture_collector(artifacts_dir))
    [nic_id] = make_ethernet_network('metrics_network', [one_vm])
    interface_name = one_vm.os_access.networking.get_interface_name(nic_id)
    os_access = one_vm.os_access
    # Test that old addresses are correctly removed from the interface.
    ip_address_params = [
        ['10.10.10.1/24'],
        ['fd00::1/8'],
        ['10.10.10.1/24', '10.10.11.1/24', '10.10.12.1/24'],
        ['fd00::1/8', 'fd00::2/8', 'fd00::3/8'],
        ['10.10.10.10/24', 'fd00::1/8'],
        ]
    for ip_addresses in ip_address_params:
        ip_addresses = [ip_interface(ip) for ip in ip_addresses]
        os_access.networking.setup_static_ip(nic_id, *ip_addresses)
        actual_ip_addresses = _get_manually_set_ip_addresses(interface_name, os_access)
        assert set(actual_ip_addresses) == set(ip_addresses)
        os_access.reboot()
        actual_ip_addresses = _get_manually_set_ip_addresses(interface_name, os_access)
        assert set(actual_ip_addresses) == set(ip_addresses)


def test_get_ip_ubuntu18_multiple(exit_stack):
    _test_get_ip('ubuntu18', ['10.0.153.1/22', '10.0.153.5/14', 'fd00::1/16', 'fd00::5/20'], exit_stack)


def test_get_ip_win11_multiple(exit_stack):
    _test_get_ip('win11', ['10.0.153.1/22', '10.0.153.5/14', 'fd00::1/16', 'fd00::5/20'], exit_stack)


def test_get_ip_ubuntu18_ipv4(exit_stack):
    _test_get_ip('ubuntu18', ['10.0.153.1/22'], exit_stack)


def test_get_ip_win11_ipv4(exit_stack):
    _test_get_ip('win11', ['10.0.153.1/22'], exit_stack)


def test_get_ip_ubuntu18_ipv6(exit_stack):
    _test_get_ip('ubuntu18', ['fd00::1/16'], exit_stack)


def test_get_ip_win11_ipv6(exit_stack):
    _test_get_ip('win11', ['fd00::1/16'], exit_stack)


def test_get_ip_ubuntu18_empty(exit_stack):
    _test_get_ip('ubuntu18', [], exit_stack)


def test_get_ip_win11_empty(exit_stack):
    _test_get_ip('win11', [], exit_stack)


def _test_get_ip(one_vm_type, ip_addresses, exit_stack):
    artifacts_dir = get_run_dir()
    vm_pool = public_default_vm_pool(artifacts_dir)
    one_vm = exit_stack.enter_context(vm_pool.clean_vm(vm_types[one_vm_type]))
    one_vm.ensure_started(artifacts_dir)
    exit_stack.enter_context(one_vm.os_access.prepared_one_shot_vm(artifacts_dir))
    exit_stack.enter_context(one_vm.os_access.traffic_capture_collector(artifacts_dir))
    [nic_id] = make_ethernet_network('metrics_network', [one_vm])
    os_access = one_vm.os_access
    ip_addresses = [ip_interface(ip) for ip in ip_addresses]
    ipv4_addresses = {ip for ip in ip_addresses if isinstance(ip, IPv4Interface)}
    os_access.networking.setup_static_ip(nic_id, *ip_addresses)
    actual_ip_addresses = os_access.networking.get_ip_addresses()
    assert set(actual_ip_addresses) == ipv4_addresses
