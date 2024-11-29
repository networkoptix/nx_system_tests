# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from vm.default_vm_pool import public_default_vm_pool
from vm.default_vm_pool import vm_types
from vm.networks import make_ethernet_network


def one_running_mediaserver_two_nics(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    artifacts_dir = get_run_dir()
    vm_pool = public_default_vm_pool(artifacts_dir)
    one_vm = exit_stack.enter_context(vm_pool.clean_vm(vm_types[one_vm_type]))
    one_vm.ensure_started(artifacts_dir)
    exit_stack.enter_context(one_vm.os_access.prepared_one_shot_vm(artifacts_dir))
    exit_stack.enter_context(one_vm.os_access.traffic_capture_collector(artifacts_dir))
    [nic_id] = make_ethernet_network('metrics_network', [one_vm])
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    mediaserver = exit_stack.enter_context(pool.mediaserver_allocation(one_vm.os_access))
    mediaserver.start()
    mediaserver.api.setup_local_system()
    return mediaserver, nic_id


def network_metrics_are_updated(mediaserver_api, server_id, interface_name):
    interface_dict = get_network_interface_metrics(
        mediaserver_api, server_id, interface_name)
    if not link_is_up(interface_dict):
        return False
    return 'display_address' in interface_dict


def get_network_interface_metrics(mediaserver_api, server_id, interface_name):
    try:
        network_interfaces = mediaserver_api.get_metrics('network_interfaces')
    except KeyError:
        return None
    if (server_id, interface_name) not in network_interfaces:
        return None
    return network_interfaces[server_id, interface_name]


def link_is_up(interface_dict):
    if interface_dict is None:
        return False
    return interface_dict.get('state') == 'Up'
