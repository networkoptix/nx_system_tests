# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import Permissions
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.single_server.permissions.common import USER_PERMISSIONS


def _test_can_change_user_role(distrib_url, one_vm_type, api_version, testee, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    distrib = installer_supplier.distrib()
    distrib.assert_api_support(api_version, 'users')
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    mediaserver = one_mediaserver.mediaserver()
    audit_trail = mediaserver.api.audit_trail()

    user = mediaserver.api.add_local_user(
        f'test_{testee}_created_by_system_admin', "irrelevant",
        permissions=USER_PERMISSIONS[testee],
        )
    group_id = mediaserver.api.add_user_group(
        'test_user_group_created_by_system_admin', [Permissions.NO_GLOBAL])
    mediaserver.api.set_user_group(user.id, group_id=group_id)
    record_sequence = audit_trail.wait_for_sequence()

    for record in record_sequence:
        assert record.type == mediaserver.api.audit_trail_events.USER_UPDATE
        assert record.resources == [user.id]

    # VMS-31952: Setting the same group again (or a different group) should work.
    mediaserver.api.set_user_group(user.id, group_id=group_id)
