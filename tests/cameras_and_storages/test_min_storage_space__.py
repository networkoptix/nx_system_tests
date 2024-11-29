# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def _setup_storages(mediaserver, min_storage_space=None):
    if min_storage_space is None:
        conf_doc = mediaserver.api.get_conf_doc()
        min_storage_space = int(conf_doc['minStorageSpace']['defaultValue'])
    else:
        mediaserver.update_conf({'minStorageSpace': min_storage_space})
        mediaserver.stop()
        mediaserver.start()
    small_size = int(min_storage_space * 0.8)
    large_size = int(min_storage_space * 1.2)
    small_path = mediaserver.os_access.mount_fake_disk('S', small_size)
    large_path = mediaserver.os_access.mount_fake_disk('L', large_size)
    storages = mediaserver.api.list_storages(ignore_offline=True)
    small_visible = bool([s for s in storages if str(small_path) in s.path])
    [large] = [s for s in storages if str(large_path) in s.path]
    assert not large.is_backup
    max_file_system_footprint = max(50 * 1024**2, large_size * 0.1)
    assert large_size - max_file_system_footprint <= large.space
    mediaserver.os_access.dismount_fake_disk(small_path)
    mediaserver.os_access.dismount_fake_disk(large_path)
    return small_visible


def _test_min_storage_space(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    mediaserver = one_mediaserver.mediaserver()
    small_visible = _setup_storages(mediaserver)
    assert not small_visible
    small_visible = _setup_storages(mediaserver, min_storage_space=1024**3)
    assert not small_visible
    small_visible = _setup_storages(mediaserver, min_storage_space=100 * 1024**3)
    assert not small_visible
