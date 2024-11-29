# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from uuid import UUID

from directories import get_run_dir
from mediaserver_api import MediaserverApi
from mediaserver_api import generate_camera
from mediaserver_api import generate_mediaserver
from mediaserver_api import generate_storage
from mediaserver_api import wait_for_servers_synced
from tests.merged_systems.test_resource_synchronization.common import TEST_SIZE
from tests.merged_systems.test_resource_synchronization.common import make_env
from tests.merged_systems.test_resource_synchronization.common import merge_system_if_unmerged


def _test_remove_resource_params_data_synchronization(distrib_url, layout_file, api_version, exit_stack):
    env = make_env(distrib_url, api_version, layout_file, exit_stack)
    for idx in range(TEST_SIZE):
        server = env.servers[idx % len(env.servers)]
        api: MediaserverApi = server.api
        resource_idx = idx + 1
        camera_primary = generate_camera(resource_idx)
        api.add_generated_camera(camera_primary)
        user = api.add_generated_user(resource_idx)
        server_primary = generate_mediaserver(resource_idx)
        api.add_generated_mediaserver(server_primary)
        storage_primary = generate_storage(resource_idx, parent_id=server_primary['id'])
        api.add_generated_storage(storage_primary)
        resource_type_idx = idx % 4  # Camera, user, server or storage
        if resource_type_idx == 0:
            api.remove_camera(camera_primary['id'])
        elif resource_type_idx == 1:
            api.remove_user(user.id)
        elif resource_type_idx == 2:
            api.remove_server(server_primary['id'])
        else:
            api.remove_storage(UUID(storage_primary['id']))
    merge_system_if_unmerged(env)
    artifacts_dir = get_run_dir()
    wait_for_servers_synced(artifacts_dir, env.servers)
    for server in env.servers:
        assert not server.list_core_dumps()
