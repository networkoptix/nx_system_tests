# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from datetime import timedelta

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.waiting import wait_for_truthy


def _wait_for_login_record(api):
    audit_trail = api.audit_trail(skip_initial_records=False)
    record = audit_trail.wait_for_next()
    if record.type != api.audit_trail_events.LOGIN:
        raise RuntimeError(f'{api.audit_trail_events.LOGIN} record expected, received: {record.type}')
    return record


def _test_audit_log_expired(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    server = one_mediaserver.mediaserver()
    start_time = server.api.get_datetime()
    login_record = _wait_for_login_record(server.api)
    server.stop()
    server.os_access.set_datetime(start_time + timedelta(days=30))
    server.start()
    assert _wait_for_login_record(server.api) == login_record
    server.stop()
    server.os_access.set_datetime(start_time + timedelta(days=184))
    server.start()
    # To initiate audit log rotation we need to issue any request producing audit log event.
    # set_system_settings call is one of such requests.
    server.api.set_system_settings({'autoDiscoveryEnabled': 'false'})
    wait_for_truthy(
        lambda: _wait_for_login_record(server.api) != login_record,
        description="Old login record disappeared",
        )
