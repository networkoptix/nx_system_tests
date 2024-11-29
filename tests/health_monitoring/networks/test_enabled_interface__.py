# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from functools import partial
from ipaddress import ip_interface

from tests.health_monitoring.networks.common import network_metrics_are_updated
from tests.health_monitoring.networks.common import one_running_mediaserver_two_nics
from tests.waiting import WaitTimeout
from tests.waiting import wait_for_truthy


def _ensure_no_traffic(mediaserver_api, server_id, interface_name):

    def _get_rates():
        return mediaserver_api.get_metrics(
            'network_interfaces', (server_id, interface_name), 'rates')

    def _no_traffic():
        rates = _get_rates()
        return rates['in_kbit'] == 0 and rates['out_kbit'] == 0
    try:
        wait_for_truthy(_no_traffic, timeout_sec=150)
    except WaitTimeout:
        rates = _get_rates()
        assert rates['in_kbit'] == 0 and rates['out_kbit'] == 0


def _test_enabled_interface(distrib_url, one_vm_type, api_version, exit_stack):
    mediaserver, nic_id = one_running_mediaserver_two_nics(distrib_url, one_vm_type, api_version, exit_stack)
    server_id = mediaserver.api.get_server_id()
    interface_name = mediaserver.os_access.networking.get_interface_name(nic_id)
    mediaserver.os_access.networking.setup_static_ip(nic_id, ip_interface('10.10.10.10/24'))
    mediaserver.os_access.networking.disable_outbound_non_unicast()
    wait_for_truthy(
        network_metrics_are_updated,
        args=(mediaserver.api, server_id, interface_name))
    get_network_interface = partial(
        mediaserver.api.get_metrics, 'network_interfaces', (server_id, interface_name))
    wait_for_truthy(
        lambda: 'rates' in get_network_interface(),
        description="Rates in interface",
        timeout_sec=10)
    interface = get_network_interface()
    actual_data = {'name': interface['name'], 'state': interface['state']}
    assert {'name': interface_name, 'state': 'Up'} == actual_data
    _ensure_no_traffic(mediaserver.api, server_id, interface_name)
