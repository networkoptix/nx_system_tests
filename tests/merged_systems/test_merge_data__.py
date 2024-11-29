# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import camera_differ
from mediaserver_api import resource_params_differ
from mediaserver_api import server_differ
from mediaserver_api import storage_differ
from mediaserver_api import user_differ
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.waiting import Wait

_logger = logging.getLogger(__name__)


def _test_responses_are_equal(distrib_url, layout_file, first_alias, second_alias, api_version, exit_stack):
    layout = _layouts[layout_file]
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    [system, _, _] = exit_stack.enter_context(pool.system(layout))
    wait = Wait("until responses become equal")
    [first, second] = [system[first_alias], system[second_alias]]
    while True:
        if first.api.get_local_system_id() == second.api.get_local_system_id():
            full_diff = {
                'servers': server_differ.diff(
                    [server.raw_data for server in first.api.list_servers()],
                    [server.raw_data for server in second.api.list_servers()]),
                'users': user_differ.diff(
                    [user.raw_data for user in first.api.list_users()],
                    [user.raw_data for user in second.api.list_users()]),
                'cameras': camera_differ.diff(
                    [camera.raw_data for camera in first.api.list_cameras()],
                    [camera.raw_data for camera in second.api.list_cameras()]),
                'storages': storage_differ.diff(
                    first.api.list_storages_info_brief(), second.api.list_storages_info_brief()),
                'resource_params': resource_params_differ.diff(
                    first.api.list_all_resource_params(), second.api.list_all_resource_params())}
            _logger.info("Resource diff: %r", full_diff)
            if not any(diff for diff in full_diff.values()):
                break
        else:
            _logger.info("%s and %s has different local system ids", first_alias, second_alias)
        if not wait.again():
            raise RuntimeError(f"Resources are not synchronized: {full_diff}")
        wait.sleep()


_layouts = {
    'unrouted-merge_toward_proxy-request_proxy.yaml': {
        'machines': [
            {'alias': 'first', 'type': 'ubuntu22'},
            {'alias': 'second', 'type': 'ubuntu22'},
            {'alias': 'proxy', 'type': 'ubuntu22'},
            ],
        'mergers': [
            {'local': 'proxy', 'remote': 'first', 'take_remote_settings': False},
            {'local': 'proxy', 'remote': 'second', 'take_remote_settings': False},
            ],
        'networks': {
            '10.254.0.0/28': {'first': None, 'proxy': None},
            '10.254.0.16/28': {'proxy': None, 'second': None}}},
    'nat-merge_toward_inner.yaml': {
        'machines': [
            {'alias': 'outer', 'type': 'ubuntu22'},
            {'alias': 'inner', 'type': 'ubuntu22'},
            {'alias': 'router', 'type': 'ubuntu22'},
            ],
        'mergers': [
            {'local': 'inner', 'remote': 'outer', 'take_remote_settings': False},
            ],
        'networks': {
            '10.254.0.0/28': {
                'outer': None,
                'router': {'10.254.0.16/28': {'inner': None}}}}},
    'direct-merge_toward_requested.yaml': {
        'machines': [
            {'alias': 'first', 'type': 'ubuntu22'},
            {'alias': 'second', 'type': 'ubuntu22'},
            ],
        'mergers': [
            {'local': 'second', 'remote': 'first', 'take_remote_settings': False},
            ],
        'networks': {'10.254.0.0/28': {'first': None, 'second': None}}},
    'unrouted-merge_toward_proxy-request_sides.yaml': {
        'machines': [
            {'alias': 'first', 'type': 'ubuntu22'},
            {'alias': 'second', 'type': 'ubuntu22'},
            {'alias': 'proxy', 'type': 'ubuntu22'},
            ],
        'mergers': [
            {'local': 'first', 'network': '10.254.0.0/28', 'remote': 'proxy', 'take_remote_settings': True},
            {'local': 'second', 'network': '10.254.0.16/28', 'remote': 'proxy', 'take_remote_settings': True},
            ],
        'networks': {
            '10.254.0.0/28': {'first': None, 'proxy': None},
            '10.254.0.16/28': {'proxy': None, 'second': None}}},
    'unrouted-merge_toward_sides-request_sides.yaml': {
        'machines': [
            {'alias': 'first', 'type': 'ubuntu22'},
            {'alias': 'second', 'type': 'ubuntu22'},
            {'alias': 'proxy', 'type': 'ubuntu22'},
            ],
        'mergers': [
            {'local': 'first', 'network': '10.254.0.0/28', 'remote': 'proxy', 'take_remote_settings': False},
            {'local': 'second', 'network': '10.254.0.16/28', 'remote': 'proxy', 'take_remote_settings': False},
            ],
        'networks': {
            '10.254.0.0/28': {'first': None, 'proxy': None},
            '10.254.0.16/28': {'proxy': None, 'second': None}}},
    }
