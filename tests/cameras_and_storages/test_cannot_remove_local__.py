# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import Forbidden
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.infra import assert_raises


def _test_cannot_remove_local(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    mediaserver = one_mediaserver.mediaserver()
    api = one_mediaserver.api()
    os = mediaserver.os_access
    space = 10 * 1024 ** 3
    mediaserver.update_conf({'minStorageSpace': space})
    [default_before] = api.list_storages()
    path = os.mount_fake_disk('V', int(space * 1.2))
    mediaserver.stop()
    mediaserver.start()
    [extra_before] = api.list_storages(str(path))
    with assert_raises(Forbidden):
        api.remove_storage(default_before.id)
    [extra_after] = api.list_storages(str(path))
    assert extra_before.id == extra_after.id
    [default] = api.list_storages(default_before.path)
    assert default.id == default_before.id
    assert default.path == default_before.path
    assert default.is_backup == default_before.is_backup
    assert default.space == default_before.space
    with assert_raises(Forbidden):
        api.remove_storage(extra_before.id)
    [default_after] = api.list_storages(default.path)
    assert default_before.id == default_after.id
    [extra] = api.list_storages(extra_before.path)
    assert extra.id == extra_before.id
    assert extra.path == extra_before.path
    assert extra.is_backup == extra_before.is_backup
    assert extra.space == extra_before.space
    # TODO: Test /ec2/removeStorages endpoint.
