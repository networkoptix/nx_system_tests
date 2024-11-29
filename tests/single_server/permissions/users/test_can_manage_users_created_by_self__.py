# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def _test_can_manage_users_created_by_self(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    distrib = installer_supplier.distrib()
    distrib.assert_api_support(api_version, 'users')
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    system_admin_api = one_mediaserver.mediaserver().api
    system_admin_api.setup_local_system()
    admin = system_admin_api.add_local_admin('test_admin', 'WellKnownPassword2')
    admin_api = system_admin_api.as_user(admin)
    # Can create users.
    audit_trail = admin_api.audit_trail()
    first_user = admin_api.add_local_user('test_user_1', 'irrelevant')
    record = audit_trail.wait_for_one()
    assert record.type == system_admin_api.audit_trail_events.USER_UPDATE
    assert record.resources == [first_user.id]
    second_user = admin_api.add_local_user('test_user_2', 'irrelevant')
    record = audit_trail.wait_for_one()
    assert record.type == system_admin_api.audit_trail_events.USER_UPDATE
    assert record.resources == [second_user.id]
    # Can edit user created by self.
    admin_api.set_user_email(first_user.id, 'user-id-1@example.com')
    record = audit_trail.wait_for_one()
    assert record.type == system_admin_api.audit_trail_events.USER_UPDATE
    assert record.resources == [first_user.id]
    server_id = admin_api.get_server_id()
    admin_api.set_user_access_rights(first_user.id, [server_id])
    if api_version != 'v0':
        # Starting with APIv1, setting access rights for users
        # changes the users themselves. Therefore, the USER_UPDATE event
        # is expected to occur.
        record = audit_trail.wait_for_one()
        assert record.type == system_admin_api.audit_trail_events.USER_UPDATE
        assert record.resources == [first_user.id]
    # Can remove user created by self.
    admin_api.remove_user(first_user.id)
    record = audit_trail.wait_for_one()
    assert record.type == system_admin_api.audit_trail_events.USER_REMOVE
    assert record.resources == [first_user.id]
    admin_api.remove_user(second_user.id)
    record = audit_trail.wait_for_one()
    assert record.type == system_admin_api.audit_trail_events.USER_REMOVE
    assert record.resources == [second_user.id]
