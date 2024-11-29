# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import Forbidden
from mediaserver_api import NotFound
from mediaserver_api import SYSTEM_ADMIN_USER_ID
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.infra import assert_raises


def _test_user_manage(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    system_admin_api = one_mediaserver.mediaserver().api
    system_admin_api.setup_local_system()

    admin = system_admin_api.add_local_admin('admin_testee', 'pass')
    viewer = system_admin_api.add_local_viewer('viewer', 'pass')
    live_viewer = system_admin_api.add_local_live_viewer('live_viewer', 'pass')
    adv_viewer = system_admin_api.add_local_advanced_viewer('adv_viewer', 'pass')

    with assert_raises((Forbidden, NotFound)):
        system_admin_api.remove_user(SYSTEM_ADMIN_USER_ID)

    test_viewer = system_admin_api.add_local_viewer('test_viewer', 'WellKnownPassword2')
    viewer_api = system_admin_api.as_user(test_viewer)
    with assert_raises((Forbidden, NotFound)):
        viewer_api.add_local_admin('uncreated', 'WellKnownPassword3')
    with assert_raises((Forbidden, NotFound)):
        viewer_api.add_local_viewer('uncreated', 'WellKnownPassword3')
    with assert_raises((Forbidden, NotFound)):
        viewer_api.add_local_live_viewer('uncreated', 'WellKnownPassword3')
    with assert_raises((Forbidden, NotFound)):
        viewer_api.add_local_advanced_viewer('uncreated', 'WellKnownPassword3')
    with assert_raises((Forbidden, NotFound)):
        viewer_api.set_user_email(admin.id, 'user@example.com')
    with assert_raises((Forbidden, NotFound)):
        viewer_api.set_user_email(viewer.id, 'user@example.com')
    with assert_raises((Forbidden, NotFound)):
        viewer_api.set_user_email(live_viewer.id, 'user@example.com')
    with assert_raises((Forbidden, NotFound)):
        viewer_api.set_user_email(adv_viewer.id, 'user@example.com')
    with assert_raises((Forbidden, NotFound)):
        viewer_api.remove_user(admin.id)
    with assert_raises((Forbidden, NotFound)):
        viewer_api.remove_user(viewer.id)
    with assert_raises((Forbidden, NotFound)):
        viewer_api.remove_user(live_viewer.id)
    with assert_raises((Forbidden, NotFound)):
        viewer_api.remove_user(adv_viewer.id)
    with assert_raises((Forbidden, NotFound)):
        viewer_api.remove_user(SYSTEM_ADMIN_USER_ID)

    test_live_viewer = system_admin_api.add_local_live_viewer('test_live_viewer', 'WellKnownPassword2')
    live_viewer_api = system_admin_api.as_user(test_live_viewer)
    with assert_raises((Forbidden, NotFound)):
        live_viewer_api.add_local_admin('uncreated', 'WellKnownPassword3')
    with assert_raises((Forbidden, NotFound)):
        live_viewer_api.add_local_viewer('uncreated', 'WellKnownPassword3')
    with assert_raises((Forbidden, NotFound)):
        live_viewer_api.add_local_live_viewer('uncreated', 'WellKnownPassword3')
    with assert_raises((Forbidden, NotFound)):
        live_viewer_api.add_local_advanced_viewer('uncreated', 'WellKnownPassword3')
    with assert_raises((Forbidden, NotFound)):
        live_viewer_api.set_user_email(admin.id, 'user@example.com')
    with assert_raises((Forbidden, NotFound)):
        live_viewer_api.set_user_email(viewer.id, 'user@example.com')
    with assert_raises((Forbidden, NotFound)):
        live_viewer_api.set_user_email(live_viewer.id, 'user@example.com')
    with assert_raises((Forbidden, NotFound)):
        live_viewer_api.set_user_email(adv_viewer.id, 'user@example.com')
    with assert_raises((Forbidden, NotFound)):
        live_viewer_api.remove_user(admin.id)
    with assert_raises((Forbidden, NotFound)):
        live_viewer_api.remove_user(viewer.id)
    with assert_raises((Forbidden, NotFound)):
        live_viewer_api.remove_user(live_viewer.id)
    with assert_raises((Forbidden, NotFound)):
        live_viewer_api.remove_user(adv_viewer.id)
    with assert_raises((Forbidden, NotFound)):
        live_viewer_api.remove_user(SYSTEM_ADMIN_USER_ID)

    test_adv_viewer = system_admin_api.add_local_advanced_viewer('test_advanced_viewer', 'WellKnownPassword2')
    adv_viewer_api = system_admin_api.as_user(test_adv_viewer)
    with assert_raises((Forbidden, NotFound)):
        adv_viewer_api.add_local_admin('uncreated', 'WellKnownPassword3')
    with assert_raises((Forbidden, NotFound)):
        adv_viewer_api.add_local_viewer('uncreated', 'WellKnownPassword3')
    with assert_raises((Forbidden, NotFound)):
        adv_viewer_api.add_local_live_viewer('uncreated', 'WellKnownPassword3')
    with assert_raises((Forbidden, NotFound)):
        adv_viewer_api.add_local_advanced_viewer('uncreated', 'WellKnownPassword3')
    with assert_raises((Forbidden, NotFound)):
        adv_viewer_api.set_user_email(admin.id, 'user@example.com')
    with assert_raises((Forbidden, NotFound)):
        adv_viewer_api.set_user_email(viewer.id, 'user@example.com')
    with assert_raises((Forbidden, NotFound)):
        adv_viewer_api.set_user_email(live_viewer.id, 'user@example.com')
    with assert_raises((Forbidden, NotFound)):
        adv_viewer_api.set_user_email(adv_viewer.id, 'user@example.com')
    with assert_raises((Forbidden, NotFound)):
        adv_viewer_api.remove_user(admin.id)
    with assert_raises((Forbidden, NotFound)):
        adv_viewer_api.remove_user(viewer.id)
    with assert_raises((Forbidden, NotFound)):
        adv_viewer_api.remove_user(live_viewer.id)
    with assert_raises((Forbidden, NotFound)):
        adv_viewer_api.remove_user(adv_viewer.id)
    with assert_raises((Forbidden, NotFound)):
        adv_viewer_api.remove_user(SYSTEM_ADMIN_USER_ID)

    test_admin = system_admin_api.add_local_admin('test_admin', 'WellKnownPassword2')
    admin_api = system_admin_api.as_user(test_admin)
    testee = admin_api.add_local_viewer('viewer_by_admin', 'WellKnownPassword3')
    testee_api = admin_api.as_user(testee)
    assert testee_api.credentials_work()
    live_viewer_by_admin = admin_api.add_local_live_viewer('live_viewer_by_admin', 'WellKnownPassword3')
    live_viewer_by_admin_api = admin_api.as_user(live_viewer_by_admin)
    assert live_viewer_by_admin_api.credentials_work()
    adv_viewer_by_admin = admin_api.add_local_advanced_viewer('adv_viewer_by_admin', 'WellKnownPassword3')
    adv_viewer_api = admin_api.as_user(adv_viewer_by_admin)
    assert adv_viewer_api.credentials_work()
    admin_api.set_user_email(viewer.id, 'user@example.com')
    admin_api.set_user_email(live_viewer.id, 'user@example.com')
    admin_api.set_user_email(adv_viewer.id, 'user@example.com')
    with assert_raises((Forbidden, NotFound)):
        admin_api.add_local_admin('uncreated', 'WellKnownPassword3')
    with assert_raises((Forbidden, NotFound)):
        admin_api.set_user_email(admin.id, 'user@example.com')
    with assert_raises((Forbidden, NotFound)):
        admin_api.remove_user(admin.id)
    with assert_raises((Forbidden, NotFound)):
        admin_api.remove_user(SYSTEM_ADMIN_USER_ID)
    admin_api.remove_user(viewer.id)
    admin_api.remove_user(live_viewer.id)
    admin_api.remove_user(adv_viewer.id)
