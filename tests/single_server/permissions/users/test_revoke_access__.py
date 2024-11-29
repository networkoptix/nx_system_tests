# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import Permissions
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def _test_revoke_access(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    system_admin_api = one_mediaserver.mediaserver().api
    system_admin_api.setup_local_system()

    test_user = system_admin_api.add_local_user('testuser', 'irrelevant', [Permissions.CUSTOM_USER])
    test_user_api = system_admin_api.as_user(test_user)

    test_layout_id = system_admin_api.add_layout('test_layout')
    assert system_admin_api.get_layout(test_layout_id) is not None

    [test_camera] = system_admin_api.add_test_cameras(offset=0, count=1)

    assert test_user_api.get_layout(test_layout_id) is None
    assert test_user_api.get_camera(test_camera.id) is None

    system_admin_api.set_user_access_rights(test_user.id, [test_layout_id, test_camera.id])

    layout = test_user_api.get_layout(test_layout_id)
    assert layout is not None
    assert layout.id == test_layout_id

    camera = test_user_api.get_camera(test_camera.id)
    assert camera is not None
    assert camera.id == test_camera.id

    system_admin_api.revoke_access_rights(test_user.id)

    assert test_user_api.get_layout(test_layout_id) is None
    assert test_user_api.get_camera(test_camera.id) is None
