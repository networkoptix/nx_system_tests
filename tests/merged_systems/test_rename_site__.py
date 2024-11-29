# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def _test_rename_site(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    mediaserver = one_mediaserver.mediaserver()
    audit_trail = mediaserver.api.audit_trail()
    old_site_name = mediaserver.api.get_site_name()
    new_site_name = 'new-site-name'
    mediaserver.api.rename_site(new_site_name)
    record_sequence = audit_trail.wait_for_sequence()
    expected_sequence = [mediaserver.api.audit_trail_events.SITE_NAME_CHANGED]
    assert [rec.type for rec in record_sequence] == expected_sequence
    params_expected = f'description={old_site_name} -> {new_site_name}'
    assert record_sequence[0].params == params_expected
    assert mediaserver.api.get_site_name() == new_site_name
