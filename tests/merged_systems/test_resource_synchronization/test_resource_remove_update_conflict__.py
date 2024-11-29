# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from typing import List
from typing import Mapping
from uuid import UUID

from directories import get_run_dir
from mediaserver_api import MediaserverApi
from mediaserver_api import generate_camera
from mediaserver_api import generate_mediaserver
from mediaserver_api import generate_storage
from mediaserver_api import wait_for_servers_synced
from tests.merged_systems.test_resource_synchronization.common import TEST_SIZE
from tests.merged_systems.test_resource_synchronization.common import make_env


def _test_resource_remove_update_conflict(distrib_url, layout_file, api_version, exit_stack):
    env = make_env(distrib_url, api_version, layout_file, exit_stack)
    cameras_data: List[Mapping[str, str]] = []
    users_data: List[Mapping[str, str]] = []
    servers_data: List[Mapping[str, str]] = []
    storages_data: List[Mapping[str, str]] = []
    for idx in range(TEST_SIZE):
        first_server = env.servers[idx % len(env.servers)]
        first_api: MediaserverApi = first_server.api
        resource_idx = idx + 1
        camera_primary = generate_camera(resource_idx)
        first_api.add_generated_camera(camera_primary)
        cameras_data.append({
            'id': camera_primary['id'],
            'name': camera_primary['name'],
            })
        user = first_api.add_generated_user(resource_idx)
        users_data.append({
            'id': user.id,
            'name': user.name,
            'password': user.password,
            })
        server_primary = generate_mediaserver(resource_idx)
        first_api.add_generated_mediaserver(server_primary)
        servers_data.append({
            'id': server_primary['id'],
            'name': server_primary['name'],
            })
        storage_primary = generate_storage(resource_idx, parent_id=server_primary['id'])
        first_api.add_generated_storage(storage_primary)
        storages_data.append({
            'id': storage_primary['id'],
            'name': server_primary['name'],
            })
    artifacts_dir = get_run_dir()
    wait_for_servers_synced(artifacts_dir, env.servers)
    for idx in range(TEST_SIZE):
        first_server = env.servers[idx % len(env.servers)]
        first_api: MediaserverApi = first_server.api
        second_server = env.servers[(idx + 1) % len(env.servers)]
        second_api: MediaserverApi = second_server.api
        resource_type_idx = idx % 4  # Camera, user, server or storage
        if resource_type_idx == 0:
            camera_data = cameras_data[idx]
            new_camera_name = f'{camera_data["name"]}_changed'
            first_api.rename_camera(camera_data['id'], new_camera_name)
            second_api.remove_camera(camera_data['id'])
        elif resource_type_idx == 1:
            user_data = users_data[idx]
            new_username = f'{user_data["name"]}_changed'
            # VMS-22103, VMS-23474: Username cannot be changed without specifying password.
            user_password = user_data['password']
            first_api.set_user_credentials(user_data['id'], new_username, user_password)
            second_api.remove_user(user_data['id'])
        elif resource_type_idx == 2:
            server_data = servers_data[idx]
            new_server_name = f'{server_data["name"]}_changed'
            first_api.rename_server(new_server_name, server_id=server_data['id'])
            second_api.remove_server(server_data['id'])
        elif resource_type_idx == 3:
            storage_data = storages_data[idx]
            new_storage_name = f'{storage_data["name"]}_changed'
            first_api.rename_storage(storage_data['id'], new_storage_name)
            second_api.remove_storage(UUID(storage_data['id']))
    wait_for_servers_synced(artifacts_dir, env.servers)
    for server in env.servers:
        assert not server.list_core_dumps()
