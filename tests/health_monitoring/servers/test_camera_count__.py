# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def _test_camera_count(distrib_url, two_vm_types, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    two_mediaservers = exit_stack.enter_context(pool.two_mediaservers(two_vm_types))
    two_mediaservers.start()
    two_mediaservers.setup_system()
    two_mediaservers.merge()
    first = two_mediaservers.first.installation()
    second = two_mediaservers.second.installation()
    cameras = first.api.add_test_cameras(0, 10)
    second.api.add_test_cameras(10, 10)
    first_id = first.api.get_server_id()
    second_id = second.api.get_server_id()
    first.api.wait_for_metric('servers', first_id, 'cameras', expected=10)
    first.api.wait_for_metric('servers', second_id, 'cameras', expected=10)
    data = first.api.get_metrics('servers')
    actual_cameras = {'initial_cameras': {
        'first': data[first_id]['cameras'], 'second': data[second_id]['cameras']}}
    for camera in cameras[:5]:
        first.api.set_camera_parent(camera.id, second_id)
    data = first.api.get_metrics('servers')
    actual_cameras['after_move'] = {
        'first': data[first_id]['cameras'], 'second': data[second_id]['cameras']}
    expected_cameras = {
        'initial_cameras': {'first': 10, 'second': 10},
        'after_move': {'first': 5, 'second': 15}}
    assert actual_cameras == expected_cameras
