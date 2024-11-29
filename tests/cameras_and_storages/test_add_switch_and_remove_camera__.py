# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.merging import merge_systems
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras


def _test_add_switch_and_remove_camera(distrib_url, two_vm_types, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    camera_server = MultiPartJpegCameraServer()
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    two_mediaservers = exit_stack.enter_context(pool.two_mediaservers(two_vm_types))
    two_mediaservers.start()
    two_mediaservers.setup_system()
    one = two_mediaservers.first.installation()
    two = two_mediaservers.second.installation()
    one_guid, two_guid = one.api.get_server_id(), two.api.get_server_id()
    audit_trail = one.api.audit_trail()
    merge_systems(one, two, take_remote_settings=False)
    record = audit_trail.wait_for_one()
    assert record.type == one.api.audit_trail_events.SITES_MERGE
    [camera] = add_cameras(one, camera_server)
    camera_resource = [camera.id]
    record = audit_trail.wait_for_one()
    assert record.type == one.api.audit_trail_events.CAMERA_INSERT
    assert record.resources == camera_resource
    one.api.set_camera_preferred_parent(camera.id, one_guid)
    record = audit_trail.wait_for_one()
    assert record.type == one.api.audit_trail_events.CAMERA_UPDATE
    assert record.resources == camera_resource
    audit_trail.skip_existing_events()
    # NX client sends 2 requests to mediaserver when camera moving in the resource tree:
    #   1. ec2/saveCameraUserAttributes with new preferredId;
    #   2. ec2/saveCamera with new parentId.
    # In fact, only the first request leads to `AR_CameraUpdate` appearance in the audit log.
    one.api.set_camera_preferred_parent(camera.id, two_guid)
    two.api.set_camera_parent(camera.id, two_guid)
    record = audit_trail.wait_for_one()
    assert record.type == one.api.audit_trail_events.CAMERA_UPDATE
    assert record.resources == camera_resource
    one.api.remove_resource(camera.id)
    record = audit_trail.wait_for_one()
    assert record.type == one.api.audit_trail_events.CAMERA_REMOVE
    assert record.resources == camera_resource
