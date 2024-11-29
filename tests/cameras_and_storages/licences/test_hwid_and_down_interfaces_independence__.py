# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from vm.networks import make_ethernet_network


def _test_hwid_and_down_interfaces_independence(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    # A one VM network is set up to make sure that there is another NIC,
    # besides "host-bound", which used to access VM from the host.
    # It must be done before the mediaserver is started and set up, because
    # with KVM a new NIC is added when plugging a network, so hardware is
    # changed and, therefore, hardware id may be changed too.
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    [_nic_id_1] = make_ethernet_network('test-license-1', [one_mediaserver.vm()])
    [nic_id_2] = make_ethernet_network('test-license-2', [one_mediaserver.vm()])

    mediaserver = one_mediaserver.mediaserver()
    mediaserver.start()
    mediaserver.api.setup_local_system()

    hwids_before = mediaserver.api.list_hwids()
    mediaserver.os_access.networking.disable_interface(nic_id_2)
    hwids_after = mediaserver.api.list_hwids()
    assert set(hwids_after) == set(hwids_before)
