# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from mediaserver_api import wait_for_servers_synced
from tests.merged_systems.test_resource_synchronization.common import make_env


def _test_initial_merge(distrib_url, layout_file, api_version, exit_stack):
    env = make_env(distrib_url, api_version, layout_file, exit_stack)
    artifacts_dir = get_run_dir()
    wait_for_servers_synced(artifacts_dir, env.servers)
    for server in env.servers:
        assert not server.list_core_dumps()
