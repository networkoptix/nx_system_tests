# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from collections.abc import Mapping
from typing import Any
from uuid import UUID

from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.license_scenarios import grant_license
from mediaserver_scenarios.merging import merge_systems
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras


def _test_merge_resources(distrib_url, two_vm_types, api_version, exit_stack):
    _logger.info('Prepare the stand')
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    two_mediaservers = exit_stack.enter_context(pool.two_mediaservers(two_vm_types))
    two_mediaservers.start()
    two_mediaservers.setup_system({'licenseServer': license_server.url()})
    one = two_mediaservers.first.installation()
    two = two_mediaservers.second.installation()
    grant_license(one, license_server)
    grant_license(two, license_server)
    camera_server = MultiPartJpegCameraServer()
    _logger.info("Create the data on server 1")
    [camera1_one, camera2_one] = add_cameras(one, camera_server, indices=[1, 2])
    one.api.start_recording(camera1_one.id, fps=30, stream_quality='low')
    user1 = one.api.add_local_user('test_user1', 'irrelevant')
    one.api.set_user_access_rights(user1.id, [camera1_one.id])
    layout_id = one.api.add_generated_layout(
        _layout_with_2_resources('Layout1', camera1_one.id, camera2_one.id))
    layout1_one = one.api.get_layout(layout_id)
    _logger.info("Create the data on server 2")
    [camera1_two, camera2_two] = add_cameras(two, camera_server, indices=[1, 2])
    camera1_fps = 15
    two.api.start_recording(camera1_two.id, fps=camera1_fps, stream_quality='low')
    user2 = two.api.add_local_user('test_user2', 'irrelevant')
    two.api.set_user_access_rights(user2.id, [camera1_two.id])
    layout_id = two.api.add_layout_with_resource('Layout1', str(camera1_two.id))
    layout1_two = two.api.get_layout(layout_id)
    layout_id = two.api.add_generated_layout(
        _layout_with_2_resources('Layout2', camera1_two.id, camera2_two.id))
    layout2_two = two.api.get_layout(layout_id)
    _logger.info("Merge servers")
    merge_systems(two, one, take_remote_settings=False)
    _logger.info("Check the merged system")
    servers = one.api.list_servers()
    assert len(servers) == 2, f"Expected 2 servers in system, but got {servers}"
    _logger.info("Check users")
    users = [user for user in two.api.list_users() if not user.is_admin]
    assert len(users) == 2, f"Expected 2 users, but got {users}"
    [user_one_res] = users[0].accessible_resources.keys()
    [user_two_res] = users[1].accessible_resources.keys()
    assert camera1_one.id == user_one_res == user_two_res, (
        f"It is expected that users retains permissions to the camera {camera1_one.name}")
    _logger.info("Check layouts")
    all_layouts = {layout.id: layout for layout in one.api.list_layouts()}
    assert len(all_layouts) == 3, f"3 layouts were expected, but {all_layouts.values()} were received"
    layout = all_layouts[layout1_one.id]
    assert layout.name == layout1_one.name, (
        f"The expected layout, {layout1_one.name}, should not change its name, but it is currently "
        f"showing as {layout.name}")
    assert set(layout.resources()) == {camera1_one.id, camera2_one.id}, (
        f"Expected that {layout1_one.name} from the first server contains both cameras")
    layout = all_layouts[layout1_two.id]
    assert layout.name == layout1_two.name, (
        f"The expected layout, {layout1_two.name}, should not change its name, but it is currently "
        f"showing as {layout.name}")
    assert set(layout.resources()) == {camera1_one.id}, (
        f"Expected that {layout1_two.name} from the second server contains camera "
        f"{camera1_one.id}, but got {layout.resources()}")
    layout = all_layouts[layout2_two.id]
    assert layout.name == layout2_two.name, (
        f"The expected layout, {layout2_two.name}, should not change its name, but it is currently "
        f"showing as {layout.name}")
    assert set(layout.resources()) == {camera1_one.id, camera2_one.id}, (
        f"Expected that {layout2_two.name} from the second server contains both cameras")
    _logger.info("Check the camera recording parameters")
    camera = one.api.get_camera(camera1_one.id)
    scheduled_task = camera.schedule_tasks[0]
    assert scheduled_task['fps'] == camera1_fps, (
        f"Recoding was expected at {camera1_fps} fps, but {scheduled_task['fps']} fps was observed")


def _layout_with_2_resources(name: str, resource1: UUID, resource2: UUID) -> Mapping[str, Any]:
    layout_data = {
        'name': name,
        'items': [
            {
                'resourceId': str(resource1),
                'flags': 1,
                'left': 0, 'top': 0, 'right': 1, 'bottom': 1,
                },
            {
                'resourceId': str(resource2),
                'flags': 1,
                'left': 1, 'top': 1, 'right': 0, 'bottom': 0,
                },
            ],
        'cellAspectRatio': 1,
        'fixedWidth': 1,
        'fixedHeight': 1,
        }
    return layout_data


_logger = logging.getLogger(__name__)
