# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.merging import merge_many_servers
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import record_from_cameras
from tests.merged_systems.failover.conftest import advertise_to_change_camera_parent
from tests.merged_systems.failover.conftest import configure_license
from tests.merged_systems.failover.conftest import discover_camera


def _test_recorded_period_server_id(distrib_url, two_vm_types, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    distrib = installer_supplier.distrib()
    distrib.assert_not_older_than(
        'vms_5.1', "Recorded periods contain server ID only from version 5.1")
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    two_mediaservers = exit_stack.enter_context(pool.two_mediaservers(two_vm_types))
    two_mediaservers.start()
    one = two_mediaservers.first.installation()
    two = two_mediaservers.second.installation()
    for server in one, two:
        server.api.setup_local_system({'licenseServer': license_server.url()})
        configure_license(server, license_server)
    merge_many_servers([one, two])
    camera_server = MultiPartJpegCameraServer()
    camera = discover_camera(one, camera_server, '/test.mjpeg')
    record_from_cameras(one.api, [camera], camera_server, duration_sec=5)
    one_server_id = one.api.get_server_id()
    assert camera.parent_id == one_server_id
    [period_server_id_on_one] = one.api.list_recorded_periods_server_ids(camera.id)
    assert period_server_id_on_one == one_server_id
    [period_server_id_on_two] = two.api.list_recorded_periods_server_ids(camera.id)
    assert period_server_id_on_two == one_server_id
    two_server_id = two.api.get_server_id()
    one.api.set_camera_preferred_parent(camera.id, two_server_id)
    [camera] = advertise_to_change_camera_parent([camera], [one, two])
    assert camera.parent_id == two_server_id
    [period_server_id_on_two] = two.api.list_recorded_periods_server_ids(camera.id)
    assert period_server_id_on_two == one_server_id
    one.default_archive().camera_archive(camera.physical_id).remove()
    one.api.rebuild_main_archive()
    record_from_cameras(two.api, [camera], camera_server, duration_sec=5)
    [period_server_id_on_one] = one.api.list_recorded_periods_server_ids(camera.id)
    assert period_server_id_on_one == two_server_id
    [period_server_id_on_two] = two.api.list_recorded_periods_server_ids(camera.id)
    assert period_server_id_on_two == two_server_id
