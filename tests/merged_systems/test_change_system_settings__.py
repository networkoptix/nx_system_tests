# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def _test_change_system_settings(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    mediaserver = one_mediaserver.mediaserver()
    audit_trail = mediaserver.api.audit_trail()
    audit_trail.skip_existing_events()
    name = 'autoDiscoveryEnabled'
    value = 'false'
    mediaserver.api.set_system_settings({name: value})
    record = audit_trail.wait_for_one()
    assert record.type == mediaserver.api.audit_trail_events.SETTINGS_CHANGE
    assert mediaserver.api.get_system_settings()[name] == value
