# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import Forbidden
from mediaserver_api import Permissions
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.single_server.permissions.common import get_api_for_actor


def _test_manage_user_roles(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    distrib = installer_supplier.distrib()
    distrib.assert_api_support(api_version, 'users')
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    api = one_mediaserver.mediaserver().api
    system_admin_group_id = api.add_user_group('system_admin_group', [Permissions.NO_GLOBAL])

    viewer_api = get_api_for_actor(api, 'viewer')
    assert _try_create_group(viewer_api) is None
    assert not _can_edit_group(viewer_api, system_admin_group_id)
    assert not _can_remove_group(viewer_api, system_admin_group_id)

    live_viewer_api = get_api_for_actor(api, 'live_viewer')
    assert _try_create_group(live_viewer_api) is None
    assert not _can_edit_group(live_viewer_api, system_admin_group_id)
    assert not _can_remove_group(live_viewer_api, system_admin_group_id)

    adv_viewer_api = get_api_for_actor(api, 'advanced_viewer')
    assert _try_create_group(adv_viewer_api) is None
    assert not _can_edit_group(adv_viewer_api, system_admin_group_id)
    assert not _can_remove_group(adv_viewer_api, system_admin_group_id)

    admin_api = get_api_for_actor(api, 'admin')
    admin_group_id = _try_create_group(admin_api)
    assert _can_edit_group(admin_api, admin_group_id)
    assert _can_edit_group(admin_api, system_admin_group_id)
    assert _can_remove_group(admin_api, admin_group_id)
    assert _can_remove_group(admin_api, system_admin_group_id)


def _try_create_group(api):
    credentials = api.get_credentials()
    actor_name = credentials.username
    try:
        group_id = api.add_user_group(f'{actor_name}_group', [Permissions.ACCESS_ALL_MEDIA])
    except Forbidden:
        return None
    return group_id


def _can_edit_group(api, group_id):
    try:
        api.modify_user_group(group_id, permissions=[Permissions.EXPORT])
    except Forbidden:
        return False
    return True


def _can_remove_group(api, group_id):
    try:
        api.remove_user_group(group_id)
    except Forbidden:
        return False
    return True
