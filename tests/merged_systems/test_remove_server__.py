# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.merging import merge_systems
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def _test_remove_server(distrib_url, two_vm_types, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    two_mediaservers = exit_stack.enter_context(pool.two_mediaservers(two_vm_types))
    two_mediaservers.start()
    two_mediaservers.setup_system()
    one = two_mediaservers.first.installation()
    two = two_mediaservers.second.installation()
    audit_trail = one.api.audit_trail()
    merge_systems(one, two, take_remote_settings=False)
    second_guid = two.api.get_server_id()
    # It can lead to `400 Bad Request`, when second server removing by
    # `ec2/removeResource`, if test starts without these waits.
    one.api.wait_for_neighbors_status('Online', timeout_sec=30)
    two.api.wait_for_neighbors_status('Online', timeout_sec=30)
    second_name = 'Server with id: {}'.format(second_guid)
    one.api.rename_server(second_name, second_guid)
    two.stop()
    one.api.wait_for_neighbors_status('Offline')
    one.api.remove_resource(second_guid)
    record_sequence = audit_trail.wait_for_sequence()
    expected_sequence = [
        one.api.audit_trail_events.SITES_MERGE,
        one.api.audit_trail_events.SERVER_UPDATE,
        one.api.audit_trail_events.STORAGE_REMOVE,  # Removes the storage first
        one.api.audit_trail_events.SERVER_REMOVE,   # and then its server (VMS-19602).
        ]
    assert [rec.type for rec in record_sequence] == expected_sequence
    assert record_sequence[-1].params == 'description={}'.format(second_name)
