# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from uuid import UUID

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import SYSTEM_ADMIN_USER_ID
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


# There is a requirement - credentials should not be changed after restore from backup.
def _test_credentials_unchanged_after_restore(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    mediaserver = one_mediaserver.mediaserver()
    audit_trail = mediaserver.api.audit_trail()
    api_with_default_credentials = mediaserver.api.copy()
    assert api_with_default_credentials.credentials_work()
    backup = mediaserver.api.dump_database()
    mediaserver.api.change_admin_password('WellKnownPassword3')  # noqa SpellCheckingInspection
    [record, *extra_records] = audit_trail.wait_for_sequence()
    # After VMS-29359, changing the admin password resets the allowed authentication types.
    # This behavior is handled in change_admin_password(), which enables the required
    # authentication types. During this enabling, an additional USER_UPDATE record appears.
    [enabling_basic_and_digest_auth_record] = extra_records
    assert enabling_basic_and_digest_auth_record.type == mediaserver.api.audit_trail_events.USER_UPDATE
    assert enabling_basic_and_digest_auth_record.resources == [UUID(SYSTEM_ADMIN_USER_ID)]
    assert record.type == mediaserver.api.audit_trail_events.USER_UPDATE
    assert record.resources == [UUID(SYSTEM_ADMIN_USER_ID)]
    with mediaserver.api.waiting_for_restart():
        mediaserver.api.restore_database(backup)
    assert mediaserver.api.credentials_work()
    assert not api_with_default_credentials.credentials_work()
