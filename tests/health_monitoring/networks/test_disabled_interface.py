# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import sys
import time
from ipaddress import ip_interface

from runner.ft_test import run_ft_test
from tests.base_test import VMSTest
from tests.health_monitoring.networks.common import network_metrics_are_updated
from tests.health_monitoring.networks.common import one_running_mediaserver_two_nics
from tests.waiting import wait_for_truthy


class test_ubuntu22_v0(VMSTest):
    """Test disabled interface.

    See: https://networkoptix.atlassian.net/browse/FT-680
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/58203
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/65734
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/65749
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/65755
    """

    def _run(self, args, exit_stack):
        _test_disabled_interface(args.distrib_url, 'ubuntu22', 'v0', exit_stack)


def _test_disabled_interface(distrib_url, one_vm_type, api_version, exit_stack):
    mediaserver, nic_id = one_running_mediaserver_two_nics(distrib_url, one_vm_type, api_version, exit_stack)
    server_id = mediaserver.api.get_server_id()
    interface_name = mediaserver.os_access.networking.get_interface_name(nic_id)
    mediaserver.os_access.networking.setup_static_ip(nic_id, ip_interface('10.10.10.1/24'))
    wait_for_truthy(
        network_metrics_are_updated,
        args=(mediaserver.api, server_id, interface_name))
    mediaserver.os_access.networking.disable_interface(nic_id)
    expected_data = {'name': interface_name, 'state': 'Down'}
    start = time.monotonic()
    while time.monotonic() - start < 30:
        interface = mediaserver.api.get_metrics('network_interfaces', (server_id, interface_name))
        if 'rates' not in interface:
            actual_data = {'name': interface['name'], 'state': interface['state']}
            # There can be situation for short period of time when rates are absent but
            # interface state is still 'Up'.
            if actual_data == expected_data:
                break
        time.sleep(1)
    else:
        raise RuntimeError(
            f"Disabled interface has wrong metrics: actual: {interface}; expected {expected_data}")


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_ubuntu22_v0()]))
