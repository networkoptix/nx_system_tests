# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from types import SimpleNamespace

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.merging import merge_systems
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool

TEST_SIZE = 100


def make_env(distrib_url, api_version, layout_file, exit_stack):
    layout = _layouts[layout_file]
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    [system, _, _] = exit_stack.enter_context(pool.system(layout))
    return SimpleNamespace(
        one=system['first'],
        two=system['second'],
        servers=list(system.values()),
        system_is_merged='direct-no_merge.yaml' not in layout_file,
        )


_layouts = {
    'direct-merge_toward_requested.yaml': {
        'machines': [
            {'alias': 'first', 'type': 'ubuntu22'},
            {'alias': 'second', 'type': 'ubuntu22'},
            ],
        'mergers': [
            {'local': 'second', 'remote': 'first', 'take_remote_settings': False},
            ],
        'networks': {'10.254.0.0/28': {'first': None, 'second': None}}},
    'direct-no_merge.yaml': {
        'machines': [
            {'alias': 'first', 'type': 'ubuntu22'},
            {'alias': 'second', 'type': 'ubuntu22'},
            ],
        'mergers': [],
        'networks': {'10.254.0.0/28': {'first': None, 'second': None}}},
    }


def merge_system_if_unmerged(env):
    if env.system_is_merged:
        return
    assert len(env.servers) >= 2
    for i in range(len(env.servers) - 1):
        merge_systems(env.servers[i + 1], env.servers[i], take_remote_settings=False)
        env.system_is_merged = True
