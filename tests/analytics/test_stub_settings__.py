# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
import logging
import time
from contextlib import ExitStack
from pathlib import Path
from typing import Optional

from os_access import PosixAccess
from tests.analytics.common import attribute_names
from tests.analytics.common import check_for_plugin_diagnostic_events
from tests.analytics.common import compare_settings_dicts
from tests.analytics.common import enable_device_agent
from tests.analytics.common import prepare_one_mediaserver_stand
from tests.analytics.common import recording_camera


def _engine_settings_file_is_empty(engine_id, settings_dir, plugin_name):
    file = settings_dir / f'{plugin_name}_engine_{engine_id}_effective_settings.json'
    _wait_for_file_creation(file)
    return _json_file_is_empty(file)


def _list_stub_settings_engine_settings_errors(api, engine_id, seed: int = 0):
    new = _set_random_stub_engine_settings(api, engine_id, seed)
    current = api.get_analytics_engine_settings(engine_id).values
    # Plugin/Integration-side setting has to remain unchanged.
    expected = {**new, 'testPluginSideSpinBox': 42}
    if 'testIntegrationSideSpinBox' in current and 'testPluginSideSpinBox' not in current:
        expected = {**new, 'testIntegrationSideSpinBox': 42}
        expected.pop('testPluginSideSpinBox')
    return compare_settings_dicts(expected, current)


def _list_stub_settings_agent_settings_errors(api, camera_id, engine_id, seed: int = 0):
    new_settings = _set_random_settings_for_stub_settings(api, camera_id, engine_id, seed)
    actual_settings = api.get_device_analytics_settings(camera_id, engine_id).values
    return compare_settings_dicts(new_settings, actual_settings)


def _enable_dump_plugin_settings(mediaserver):
    settings_dir = mediaserver.os_access.tmp() / 'plugins_settings'
    settings_dir.mkdir(exist_ok=True)
    if isinstance(mediaserver.os_access, PosixAccess):
        settings_dir.chmod(0o777)  # Path.mkdir(mode=0o777) sets 755
    mediaserver.stop()
    mediaserver.update_ini(
        'vms_server_plugins', {
            'analyticsSettingsOutputPath': settings_dir})
    mediaserver.start()
    return settings_dir


def _wait_for_file_creation(file: Path, timeout_sec=10):
    start_time = time.monotonic()
    while True:
        if file.exists():
            return
        if time.monotonic() - start_time > timeout_sec:
            raise RuntimeError(
                f"File {file} not created after {timeout_sec}s")
        time.sleep(1)


def _json_file_is_empty(file: Path):
    content = json.loads(file.read_text())
    if not content:
        return True
    return False


def _agent_settings_file_is_empty(camera_id, settings_dir, plugin_name):
    file = settings_dir / f'{plugin_name}_device_{camera_id}_effective_settings.json'
    _wait_for_file_creation(file)
    return _json_file_is_empty(file)


def _set_random_stub_engine_settings(api, engine_id, seed: int = 0):
    # Sample plugin doesn't have any Engine settings, so this function tests only Stub plugin
    new_settings = {  # TODO: make a test for disableStreamSelection
        'testCheckBox': [True, False][seed % 2],
        'testComboBox': ['value1', 'value2', 'value3'][seed % 3],
        'testDoubleSpinBox': [3.1415, 2.7183][seed % 2],
        'testSpinBox': seed % 100,
        'text': f'NEW text {seed}',
        'testPluginSideSpinBox': seed % 100,
        }
    api.set_analytics_engine_settings(engine_id, new_settings)
    return new_settings


def _set_random_settings_for_stub_settings(api, camera_id, engine_id, seed: int = 0):
    new_settings = {
        'testCheckBox2': [True, False][seed % 2],
        'testCheckBox3': [True, False][seed % 2],
        'testCheckBoxGroup': [['Coleoidea', 'Nautiloidea'], ['Orthoceratoidea']][seed % 2],
        'testComboBox': ['value1', 'value2', 'value3'][seed % 3],
        'testComboBox2': ['value1', 'value2', 'value3'][seed % 3],
        'testDoubleSpinBox2': [3.1415, 2.7183][seed % 2],
        'testRadioButtonGroup': ['S_calloviense', 'K_medea', 'K_posterior'][seed % 3],
        'testSpinBox3': seed % 100,
        'testSwitch': [True, False][seed % 2],
        'testTextField': f'NEW text {seed}',
        'testTextFieldWithValidation': f'45ffeaa{seed % 100}',
        }
    _logger.info(
        "Applying new DeviceAgent settings for device %s, engine %s", camera_id, engine_id)
    api.set_device_analytics_settings(camera_id, engine_id, new_settings)
    return new_settings


def _test_stub_settings(
        distrib_url: str,
        vm_type: str,
        api_version: str,
        exit_stack: ExitStack,
        with_plugins_from_release: Optional[str] = None,
        ):
    stand = prepare_one_mediaserver_stand(
        distrib_url, vm_type, api_version, exit_stack, with_plugins_from_release)
    mediaserver = stand.mediaserver()
    recording_camera_id = exit_stack.enter_context(recording_camera(mediaserver)).id
    errors_dict = {}
    settings_dir = _enable_dump_plugin_settings(mediaserver)
    engine_collection = mediaserver.api.get_analytics_engine_collection()
    engine = engine_collection.get_stub('Settings')
    enable_device_agent(
        mediaserver.api, engine.name(), recording_camera_id)
    exit_stack.callback(
        check_for_plugin_diagnostic_events, mediaserver.api)
    default_engine_settings_empty = _engine_settings_file_is_empty(
        engine.id(), settings_dir, attribute_names.internal_stub_settings_name)
    if default_engine_settings_empty:
        errors_dict['Default engine settings empty'] = True
    engine_settings_errors = _list_stub_settings_engine_settings_errors(
        mediaserver.api, engine.id(), seed=1)
    if engine_settings_errors:
        errors_dict['Engine settings errors'] = engine_settings_errors
    default_agent_settings_empty = _agent_settings_file_is_empty(
        recording_camera_id, settings_dir, attribute_names.internal_stub_settings_name)
    if default_agent_settings_empty:
        errors_dict['Default Agent settings empty'] = True
    agent_settings_errors = _list_stub_settings_agent_settings_errors(
        mediaserver.api, recording_camera_id, engine.id())
    if agent_settings_errors:
        errors_dict['Agent settings errors'] = agent_settings_errors
    assert not errors_dict, f'Errors found: {errors_dict}'


_logger = logging.getLogger(__name__)
