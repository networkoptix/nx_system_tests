# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.storage_preparation import add_local_storage


def _test_storage_count_less_than_min_space(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    mediaserver = one_mediaserver.mediaserver()
    api = one_mediaserver.api()
    # minStorageSpace is 10 GB by default
    big_storage_path = add_local_storage(mediaserver, storage_size_bytes=30 * 1024**3)
    small_storage_path = add_local_storage(
        mediaserver, storage_size_bytes=3 * 1024**3)
    storages = api.list_storages()
    assert any(s.path.startswith(str(big_storage_path)) for s in storages)
    assert not any(s.path.startswith(str(small_storage_path)) for s in storages)
    assert api.get_metrics('system_info', 'storages') == 2
