# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from mediaserver_api import MediaserverApi
from mediaserver_api import generate_camera
from mediaserver_api import generate_mediaserver
from mediaserver_api import wait_for_servers_synced
from tests.merged_systems.test_resource_synchronization.common import TEST_SIZE
from tests.merged_systems.test_resource_synchronization.common import make_env
from tests.merged_systems.test_resource_synchronization.common import merge_system_if_unmerged


def _test_resource_params_data_synchronization(distrib_url, layout_file, api_version, exit_stack):
    env = make_env(distrib_url, api_version, layout_file, exit_stack)
    for idx in range(TEST_SIZE):
        server = env.servers[idx % len(env.servers)]
        api: MediaserverApi = server.api
        resource_idx = idx + 1
        server_primary = generate_mediaserver(resource_idx)
        api.add_generated_mediaserver(server_primary)
        camera_primary = generate_camera(resource_idx)
        api.add_generated_camera(camera_primary)
        user = api.add_generated_user(resource_idx)
        resource_type_idx = idx % 3  # Camera, user or server
        if resource_type_idx == 0:
            camera_id = camera_primary['id']
            new_camera_name = f'Resource_{camera_id}'
            api.rename_camera(camera_id, new_camera_name)
        elif resource_type_idx == 1:
            user_id = user.id
            # VMS-22103, VMS-23474: Username cannot be changed without specifying user password.
            user_password = user.password
            new_username = f'Resource_{user_id}'
            api.set_user_credentials(user_id, new_username, user_password)
        else:
            server_id = server_primary['id']
            new_server_name = f'Resource_{server_id}'
            api.rename_server(new_server_name, server_id=server_id)
    merge_system_if_unmerged(env)
    artifacts_dir = get_run_dir()
    wait_for_servers_synced(artifacts_dir, env.servers)
    for server in env.servers:
        assert not server.list_core_dumps()
