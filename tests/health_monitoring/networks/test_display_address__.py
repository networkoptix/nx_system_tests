# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time
from ipaddress import ip_interface

from tests.health_monitoring.networks.common import get_network_interface_metrics
from tests.health_monitoring.networks.common import link_is_up
from tests.health_monitoring.networks.common import one_running_mediaserver_two_nics
from tests.infra import Failure


def _test_display_address(distrib_url, one_vm_type, api_version, ip_addresses, exit_stack):
    ip_interfaces = [ip_interface(ip) for ip in ip_addresses]
    mediaserver, nic_id = one_running_mediaserver_two_nics(distrib_url, one_vm_type, api_version, exit_stack)
    server_id = mediaserver.api.get_server_id()
    interface_name = mediaserver.os_access.networking.get_interface_name(nic_id)
    mediaserver.os_access.networking.setup_static_ip(nic_id, *ip_interfaces)
    # On the clean VM internal network's interface
    # is up with link-local IPv6 address.
    # (starting with 'fe80::', used for point to point
    # communications). Note: this is due to IPv6 autoconfiguration.
    # See: https://superuser.com/questions/33196/how-to-disable-autoconfiguration-on-ipv6-in-linux
    metrics_update_interval_sec = 15
    timeout_sec = metrics_update_interval_sec + 5
    # We wait 5 seconds additionally in case
    # of unexpected delays.
    # (For instance the load is high and
    # server couldn't process the request).
    started_at = time.monotonic()
    result = set()
    interface_dict = {}
    ip_addresses = set(str(ip.ip) for ip in ip_interfaces)
    while time.monotonic() - started_at < timeout_sec:
        time.sleep(0.1)
        interface_dict = get_network_interface_metrics(
            mediaserver.api, server_id, interface_name)
        if not link_is_up(interface_dict):
            continue
        display_address = interface_dict.get("display_address")
        other_addresses = interface_dict.get('other_addresses', [])
        result = {*other_addresses, display_address}
        if result == ip_addresses:
            break
    else:
        if result != ip_addresses:
            message = (
                f"Expected interfaces addresses {ip_addresses!r} didn't match"
                f" received from server metrics in {timeout_sec}s."
                f" Last received metric are: {result!r}."
                )
            raise Failure(message)
    # For both IP versions on the same interface, display_address is IPv4.
    # See: https://networkoptix.testrail.net/index.php?/cases/view/58214
    if any(ip_interface(ip).version == 4 for ip in interface_dict.get('other_addresses', [])):
        assert ip_interface(interface_dict['display_address']).version != 6
