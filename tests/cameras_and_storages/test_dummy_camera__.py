# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def _test_dummy_camera(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    api = one_mediaserver.mediaserver().api
    [camera_ids] = api.add_test_cameras(offset=0, count=1)
    [camera] = api.list_cameras()
    assert camera_ids.id == camera.id
    new_camera_name = 'new_camera_name'
    api.rename_camera(camera.id, new_camera_name)
    camera = api.get_camera(camera.id)
    assert camera.name == new_camera_name
    api.remove_camera(camera.id)
    assert api.get_camera(camera.id) is None
