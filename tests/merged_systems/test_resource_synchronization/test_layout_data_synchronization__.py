# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from uuid import UUID

from directories import get_run_dir
from mediaserver_api import MediaserverApi
from mediaserver_api import generate_camera
from mediaserver_api import generate_layout
from mediaserver_api import generate_layout_item
from mediaserver_api import generate_mediaserver
from mediaserver_api import wait_for_servers_synced
from tests.merged_systems.test_resource_synchronization.common import TEST_SIZE
from tests.merged_systems.test_resource_synchronization.common import make_env
from tests.merged_systems.test_resource_synchronization.common import merge_system_if_unmerged


def _test_layout_data_synchronization(distrib_url, layout_file, api_version, exit_stack):
    env = make_env(distrib_url, api_version, layout_file, exit_stack)
    admins = [user for s in env.servers for user in s.api.list_users() if user.is_admin]
    for idx in range(TEST_SIZE):
        server = env.servers[idx % len(env.servers)]
        api: MediaserverApi = server.api
        resource_idx = idx + 1

        camera_primary = generate_camera(resource_idx)
        api.add_generated_camera(camera_primary)

        user = api.add_generated_user(resource_idx)

        server_primary = generate_mediaserver(resource_idx)
        api.add_generated_mediaserver(server_primary)

        user_layout_items = [
            generate_layout_item(resource_idx, camera_primary['id']),
            generate_layout_item(resource_idx + TEST_SIZE, server_primary['id']),
            ]
        user_layout_primary = generate_layout(
            resource_idx,
            parent_id=str(user.id),
            items=user_layout_items,
            )
        api.add_generated_layout(user_layout_primary)
        if idx % 2 == 0:
            api.remove_layout(UUID(user_layout_primary['id']))

        admin_user = admins[idx % len(admins)]
        admin_layout_items = [
            generate_layout_item(resource_idx + TEST_SIZE * 2, camera_primary['id']),
            generate_layout_item(resource_idx + TEST_SIZE * 3, server_primary['id']),
            ]
        admin_layout_primary = generate_layout(
            resource_idx + TEST_SIZE,
            parent_id=str(admin_user.id),
            items=admin_layout_items,
            )
        api.add_generated_layout(admin_layout_primary)
        if idx % 2 == 0:
            api.remove_layout(UUID(admin_layout_primary['id']))

        shared_layout_items = [
            generate_layout_item(resource_idx + TEST_SIZE * 4, camera_primary['id']),
            generate_layout_item(resource_idx + TEST_SIZE * 5, server_primary['id']),
            ]
        shared_layout_primary = generate_layout(resource_idx + TEST_SIZE * 2, items=shared_layout_items)
        api.add_generated_layout(shared_layout_primary)
        if idx % 2 == 0:
            api.remove_layout(UUID(shared_layout_primary['id']))
    merge_system_if_unmerged(env)
    artifacts_dir = get_run_dir()
    wait_for_servers_synced(artifacts_dir, env.servers)
    for server in env.servers:
        assert not server.list_core_dumps()
