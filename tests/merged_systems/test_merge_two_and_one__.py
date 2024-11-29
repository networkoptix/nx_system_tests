# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.merging import merge_systems
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def _test_merge_two_systems(distrib_url, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    network_and_system = exit_stack.enter_context(pool.system({
        'networks': {
            '10.254.0.0/28': {
                'first': None,
                'second': None,
                'third': None,
                },
            },
        'machines': [
            {'alias': 'first', 'type': 'ubuntu22'},
            {'alias': 'second', 'type': 'ubuntu22'},
            {'alias': 'third', 'type': 'ubuntu22'},
            ],
        'mergers': [],
        }))
    [system, _, _] = network_and_system
    mediaservers = system.values()
    _, two, three = mediaservers
    merge_systems(two, three, take_remote_settings=False)
    two.api.wait_for_neighbors_status('Online', timeout_sec=30)
    three.api.wait_for_neighbors_status('Online', timeout_sec=30)
    # Special configuration to check two system merge.
    # The first system contains only one mediaserver,
    # the second contains two merged mediaservers.
    one, two, three = mediaservers
    audit_trail = one.api.audit_trail()
    merge_systems(one, two, take_remote_settings=False)
    third_credentials = three.api.get_credentials()
    if third_credentials.auth_type == 'bearer':
        # Since all servers on the second system changed their local system id,
        # their session tokens were marked as removed. But the API object
        # of the third server still stores such removed token due to the fact
        # that such tokens are updated in the merge_systems() and the third server
        # was not passed to it. Hence, it needs to be updated manually.
        three.api.import_auth(one.api)
    record = audit_trail.wait_for_one()
    assert record.type == one.api.audit_trail_events.SITES_MERGE
    for server in mediaservers:
        server.api.wait_for_neighbors(2)
        server.api.wait_for_neighbors_status('Online')
