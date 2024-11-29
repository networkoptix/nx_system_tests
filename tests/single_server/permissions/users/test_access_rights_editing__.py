# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import Forbidden
from mediaserver_api import NotFound
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.infra import assert_raises


def _test_access_rights_editing(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    system_admin_api = one_mediaserver.mediaserver().api
    system_admin_api.setup_local_system()

    test_admin = system_admin_api.add_local_admin('test_admin', 'WellKnownPassword2')
    admin_api = system_admin_api.as_user(test_admin)
    test_viewer = system_admin_api.add_local_viewer('test_viewer', 'WellKnownPassword2')
    viewer_api = system_admin_api.as_user(test_viewer)
    test_live_viewer = system_admin_api.add_local_live_viewer('test_live_viewer', 'WellKnownPassword2')
    live_viewer_api = system_admin_api.as_user(test_live_viewer)
    test_adv_viewer = system_admin_api.add_local_advanced_viewer('test_advanced_viewer', 'WellKnownPassword2')
    adv_viewer_api = system_admin_api.as_user(test_adv_viewer)
    admin = system_admin_api.add_local_admin('admin_testee', 'pass')
    viewer = system_admin_api.add_local_viewer('viewer', 'pass')
    live_viewer = system_admin_api.add_local_live_viewer('live_viewer', 'pass')
    adv_viewer = system_admin_api.add_local_advanced_viewer('adv_viewer', 'pass')

    server_id = system_admin_api.get_server_id()

    with assert_raises((Forbidden, NotFound)):
        viewer_api.set_user_access_rights(admin.id, [server_id])
    with assert_raises((Forbidden, NotFound)):
        viewer_api.set_user_access_rights(viewer.id, [server_id])
    with assert_raises((Forbidden, NotFound)):
        viewer_api.set_user_access_rights(live_viewer.id, [server_id])
    with assert_raises((Forbidden, NotFound)):
        viewer_api.set_user_access_rights(adv_viewer.id, [server_id])
    with assert_raises((Forbidden, NotFound)):
        live_viewer_api.set_user_access_rights(admin.id, [server_id])
    with assert_raises((Forbidden, NotFound)):
        live_viewer_api.set_user_access_rights(viewer.id, [server_id])
    with assert_raises((Forbidden, NotFound)):
        live_viewer_api.set_user_access_rights(live_viewer.id, [server_id])
    with assert_raises((Forbidden, NotFound)):
        live_viewer_api.set_user_access_rights(adv_viewer.id, [server_id])
    with assert_raises((Forbidden, NotFound)):
        adv_viewer_api.set_user_access_rights(admin.id, [server_id])
    with assert_raises((Forbidden, NotFound)):
        adv_viewer_api.set_user_access_rights(viewer.id, [server_id])
    with assert_raises((Forbidden, NotFound)):
        adv_viewer_api.set_user_access_rights(live_viewer.id, [server_id])
    with assert_raises((Forbidden, NotFound)):
        adv_viewer_api.set_user_access_rights(adv_viewer.id, [server_id])

    admin_api.set_user_access_rights(viewer.id, [server_id])
    admin_api.set_user_access_rights(live_viewer.id, [server_id])
    admin_api.set_user_access_rights(adv_viewer.id, [server_id])
