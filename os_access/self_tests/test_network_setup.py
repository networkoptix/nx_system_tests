# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from ipaddress import ip_address
from ipaddress import ip_network

from directories import get_run_dir
from os_access import PingError
from tests.infra import assert_raises
from vm.default_vm_pool import public_default_vm_pool
from vm.default_vm_pool import vm_types
from vm.networks import setup_networks

_logger = logging.getLogger(__name__)


def test_setup_basic(exit_stack):
    artifacts_dir = get_run_dir()
    vm_pool = public_default_vm_pool(artifacts_dir)
    nodes = {}
    nodes['first'] = exit_stack.enter_context(vm_pool.clean_vm(vm_types['ubuntu18']))
    nodes['second'] = exit_stack.enter_context(vm_pool.clean_vm(vm_types['ubuntu18']))
    nodes['router-1'] = exit_stack.enter_context(vm_pool.clean_vm(vm_types['ubuntu18']))
    nodes['router-2'] = exit_stack.enter_context(vm_pool.clean_vm(vm_types['ubuntu18']))
    for vm in nodes.values():
        vm.ensure_started(artifacts_dir)
        exit_stack.enter_context(vm.os_access.prepared_one_shot_vm(artifacts_dir))
        exit_stack.enter_context(vm.os_access.traffic_capture_collector(artifacts_dir))
    assignments = setup_networks(nodes, {
        '10.254.1.0/24': {
            'first': None,
            'router-1': {
                '10.254.2.0/24': {
                    'router-2': {
                        '10.254.3.0/24': {
                            'second': None}}}}}})

    assert ip_network('10.254.1.0/24') in assignments['first']
    assert ip_network('10.254.2.0/24') not in assignments['first']
    assert ip_network('10.254.3.0/24') not in assignments['first']
    assert ip_network('10.254.1.0/24') in assignments['router-1']
    assert ip_network('10.254.2.0/24') in assignments['router-1']
    assert ip_network('10.254.3.0/24') not in assignments['router-1']
    assert ip_network('10.254.1.0/24') not in assignments['router-2']
    assert ip_network('10.254.2.0/24') in assignments['router-2']
    assert ip_network('10.254.3.0/24') in assignments['router-2']
    assert ip_network('10.254.1.0/24') not in assignments['second']
    assert ip_network('10.254.2.0/24') not in assignments['second']
    assert ip_network('10.254.3.0/24') in assignments['second']

    assert assignments['router-1'][ip_network('10.254.2.0/24')][0] == ip_address('10.254.2.1')
    assert assignments['router-2'][ip_network('10.254.3.0/24')][0] == ip_address('10.254.3.1')

    nodes['second'].os_access.networking.ping(str(assignments['second'][ip_network('10.254.3.0/24')][0]))
    nodes['second'].os_access.networking.ping(str(assignments['router-2'][ip_network('10.254.3.0/24')][0]))
    nodes['second'].os_access.networking.ping(str(assignments['router-2'][ip_network('10.254.2.0/24')][0]))
    nodes['second'].os_access.networking.ping(str(assignments['router-1'][ip_network('10.254.2.0/24')][0]))
    nodes['second'].os_access.networking.ping(str(assignments['router-1'][ip_network('10.254.1.0/24')][0]))
    nodes['second'].os_access.networking.ping(str(assignments['first'][ip_network('10.254.1.0/24')][0]))
    nodes['first'].os_access.networking.ping(str(assignments['router-1'][ip_network('10.254.1.0/24')][0]))
    with assert_raises(PingError):
        nodes['first'].os_access.networking.ping(str(assignments['router-1'][ip_network('10.254.2.0/24')][0]))
    with assert_raises(PingError):
        nodes['first'].os_access.networking.ping(str(assignments['router-2'][ip_network('10.254.2.0/24')][0]))
    with assert_raises(PingError):
        nodes['first'].os_access.networking.ping(str(assignments['second'][ip_network('10.254.3.0/24')][0]))
