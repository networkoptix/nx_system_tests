# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from vm.default_vm_pool import public_default_vm_pool
from vm.default_vm_pool import vm_types


def _test_mediaserver_monitor_disk_names(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    artifacts_dir = get_run_dir()
    vm_pool = public_default_vm_pool(artifacts_dir)
    one_vm = exit_stack.enter_context(vm_pool.clean_vm(vm_types[one_vm_type]))
    one_vm.ensure_started(artifacts_dir)
    exit_stack.enter_context(one_vm.os_access.prepared_one_shot_vm(artifacts_dir))
    exit_stack.enter_context(one_vm.os_access.traffic_capture_collector(artifacts_dir))
    vm = one_vm.vm_control
    vm.add_disk('sata', 50 * 1024)
    one_vm.os_access.mount_disk('S')
    vm.add_disk('sata', 200 * 1024)
    one_vm.os_access.mount_disk('M')
    vm.add_disk('sata', 350 * 1024)
    one_vm.os_access.mount_disk('L')
    os_disk_names = set(one_vm.os_access.list_mounted_disks().values())
    assert len(os_disk_names) == 4  # 1 system and 3 additiional
    with pool.mediaserver_allocation(one_vm.os_access) as mediaserver:
        mediaserver.start()
        mediaserver.api.setup_local_system()
        statistics = mediaserver.api.get_hdd_statistics()
        disk_names = statistics.keys()
        assert disk_names == os_disk_names
