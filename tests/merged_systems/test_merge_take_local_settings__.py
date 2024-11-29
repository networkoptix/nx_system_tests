# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.merging import merge_systems
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.waiting import wait_for_truthy


def _test_merge_take_local_settings(distrib_url, two_vm_types, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    test_system_settings = {
        'cameraSettingsOptimization': 'false',
        'autoDiscoveryEnabled': 'false',
        'statisticsAllowed': 'false',
        }
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    two_mediaservers = exit_stack.enter_context(pool.two_mediaservers(two_vm_types))
    one = two_mediaservers.first.installation()
    one.start()
    one.api.setup_local_system(test_system_settings)
    two = two_mediaservers.second.installation()
    two.start()
    two.api.setup_local_system()
    settings_to_check = {k: v for k, v in one.api.get_system_settings().items() if k in test_system_settings.keys()}
    assert settings_to_check == test_system_settings

    # On each server update some globalSettings to different values
    one.api.set_system_settings({'arecontRtspEnabled': 'true', 'auditTrailEnabled': 'true'})
    two.api.set_system_settings({'arecontRtspEnabled': 'false', 'auditTrailEnabled': 'false'})

    merge_systems(two, one, take_remote_settings=False)
    _wait_for_settings_merge(one, two)
    one_settings = one.api.get_system_settings()
    assert one_settings['arecontRtspEnabled'] == 'false'
    assert one_settings['auditTrailEnabled'] == 'false'
    two_settings = two.api.get_system_settings()
    assert two_settings['arecontRtspEnabled'] == 'false'
    assert two_settings['auditTrailEnabled'] == 'false'

    # Ensure both servers are merged and sync
    one.api.set_system_settings({'arecontRtspEnabled': 'true'})
    _wait_for_settings_merge(one, two)
    assert two.api.get_system_settings()['arecontRtspEnabled'] == 'true'


def _wait_for_settings_merge(one, two):
    wait_for_truthy(
        lambda: one.api.get_system_settings() == two.api.get_system_settings(),
        description='{} and {} response identically to /api/systemSettings'.format(one, two))
