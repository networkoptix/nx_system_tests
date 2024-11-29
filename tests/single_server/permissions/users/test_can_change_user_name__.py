# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def _test_can_change_user_name(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    system_admin_api = one_mediaserver.mediaserver().api
    system_admin_api.setup_local_system()
    user = system_admin_api.add_local_admin('test_admin', 'irrelevant')
    audit_trail = system_admin_api.audit_trail()
    system_admin_api.set_user_credentials(user.id, 'New_user_name', 'irrelevant')
    record = audit_trail.wait_for_one()
    assert record.type == system_admin_api.audit_trail_events.USER_UPDATE
    assert record.resources == [user.id]
