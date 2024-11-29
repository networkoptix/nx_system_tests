# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def _test_discover_storage_with_cyrillic_in_path(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    mediaserver = one_mediaserver.mediaserver()
    vm = one_mediaserver.hardware()
    os = mediaserver.os_access
    api = one_mediaserver.api()
    cyrillic_point = 'НОВЫЙ ТОМ'
    vm.add_disk('sata', size_mb=20 * 1024)
    path = os.mount_disk(cyrillic_point)
    assert path.name == cyrillic_point
    mediaserver.start()
    api.setup_local_system()
    [storage] = api.list_storages(within_path='/mnt/')
    assert cyrillic_point in storage.path
