# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from contextlib import ExitStack
from typing import Mapping
from typing import Optional

from installation import ClassicInstallerSupplier
from tests.analytics.common import check_for_plugin_diagnostic_events
from tests.analytics.common import enable_device_agent
from tests.analytics.common import prepare_one_mediaserver_stand
from tests.analytics.common import recording_camera

_logger = logging.getLogger(__name__)

_active_checkbox_stages = {
    'init': {
        'do_set': {},
        'is_set': {'activeCheckBox': False, 'additionalCheckBox': None},
        },
    'check': {
        'do_set': {'activeCheckBox': True},
        'is_set': {'activeCheckBox': True, 'additionalCheckBox': False},
        },
    'check_additional': {
        'do_set': {'additionalCheckBox': True},
        'is_set': {'activeCheckBox': True, 'additionalCheckBox': True},
        },
    'uncheck': {
        'do_set': {'activeCheckBox': False},
        'is_set': {'activeCheckBox': False, 'additionalCheckBox': None},
        },
    }


_active_radiobutton_group_stages = {
    'init': {
        'do_set': {},
        'is_set': {'activeRadioButtonGroup': 'Some value'},
        'model_range': {
            'activeRadioButtonGroup': ['Some value', 'Show something'],
            },
        },
    'show_something_1': {
        'do_set': {'activeRadioButtonGroup': 'Show something'},
        'is_set': {'activeRadioButtonGroup': 'Show something'},
        'model_range': {
            'activeRadioButtonGroup': ['Some value', 'Show something', 'Hide me'],
            },
        },
    'some_value': {
        'do_set': {'activeRadioButtonGroup': 'Some value'},
        'is_set': {'activeRadioButtonGroup': 'Some value'},
        'model_range': {
            'activeRadioButtonGroup': ['Some value', 'Show something', 'Hide me'],
            },
        },
    'show_something_2': {
        'do_set': {'activeRadioButtonGroup': 'Show something'},
        'is_set': {'activeRadioButtonGroup': 'Show something'},
        'model_range': {
            'activeRadioButtonGroup': ['Some value', 'Show something', 'Hide me'],
            },
        },
    'hide_me': {
        'do_set': {'activeRadioButtonGroup': 'Hide me'},
        'is_set': {'activeRadioButtonGroup': 'Some value'},
        'model_range': {
            'activeRadioButtonGroup': ['Some value', 'Show something'],
            },
        },
    }


_active_combobox_group_stages = {
    'init': {
        'do_set': {},
        'is_set': {
            'activeComboBox': 'Some value',
            'additionalComboBox': None,
            },
        'model_range': {
            'activeComboBox': ['Some value', 'Show additional ComboBox'],
            },
        },
    'show_additional_combobox': {
        'do_set': {'activeComboBox': 'Show additional ComboBox'},
        'is_set': {
            'activeComboBox': 'Show additional ComboBox',
            'additionalComboBox': 'Value 1',
            },
        'model_range': {
            'activeComboBox': ['Some value', 'Show additional ComboBox'],
            'additionalComboBox': ['Value 1', 'Value 2'],
            },
        },
    'value_2': {
        'do_set': {'additionalComboBox': 'Value 2'},
        'is_set': {
            'activeComboBox': 'Show additional ComboBox',
            'additionalComboBox': 'Value 2',
            },
        'model_range': {
            'activeComboBox': ['Some value', 'Show additional ComboBox'],
            'additionalComboBox': ['Value 1', 'Value 2'],
            },
        },
    'some_value': {
        'do_set': {'activeComboBox': 'Some value'},
        'is_set': {
            'activeComboBox': 'Some value',
            'additionalComboBox': None,
            },
        'model_range': {
            'activeComboBox': ['Some value', 'Show additional ComboBox'],
            },
        },
    }


def _check_settings(expected: Mapping, actual: Mapping):
    errors = {}
    for setting, expected_value in expected.items():
        actual_value = actual.get(setting)
        if actual_value is None and expected_value is None:
            continue
        if actual_value == expected_value:
            continue
        errors.update({
            setting: {
                'expected': expected_value,
                'actual': actual_value,
                }})
    return errors


def _check_active_setting_for_engine(api, engine_id, stages: Mapping):
    errors = {}
    engine_settings = api.get_analytics_engine_settings(engine_id)
    for stage, actions in stages.items():
        if actions['do_set']:
            [setting_name] = actions['do_set'].keys()
            [setting_value] = actions['do_set'].values()
            engine_settings = api.notify_engine_active_setting_changed(
                engine_id, engine_settings, setting_name, setting_value)
        stage_errors = _check_settings(actions['is_set'], engine_settings.values)
        if stage_errors:
            errors[stage] = stage_errors
    return errors


def _check_active_setting_for_agent(api, camera_id, engine_id, stages: Mapping):
    errors = {}
    agent_settings = api.get_device_analytics_settings(camera_id, engine_id)
    for stage, actions in stages.items():
        if actions['do_set']:
            [setting_name] = actions['do_set'].keys()
            [setting_value] = actions['do_set'].values()
            agent_settings = api.notify_device_active_setting_changed(
                camera_id, engine_id, agent_settings, setting_name, setting_value)
        stage_errors = _check_settings(actions['is_set'], agent_settings.values)
        if stage_errors:
            errors[stage] = stage_errors
    return errors


def _check_model_data(actual, expected):
    errors = {}
    for name, expected_value in expected.items():
        [item] = [
            item for item in actual['items']
            if item.get('name') == name
            ]
        actual_value = item['range']
        if expected_value != actual_value:
            errors.update({
                name: {
                    'expected': expected_value,
                    'actual': actual_value,
                    }})
    return errors


def _check_active_group_stage(
        expected_settings, actual_settings, expected_model_data, actual_model_data):
    errors = {}
    settings_errors = _check_settings(expected_settings, actual_settings)
    if settings_errors:
        errors = {'settings': settings_errors}
    model_errors = _check_model_data(actual_model_data, expected_model_data)
    if model_errors:
        errors.update({'model': model_errors})
    return errors


def _check_active_group_for_engine(api, engine_id, stages: Mapping):
    errors = {}
    settings_data = api.get_analytics_engine_settings(engine_id)
    for stage, actions in stages.items():
        if actions['do_set']:
            [setting_name] = actions['do_set'].keys()
            [setting_value] = actions['do_set'].values()
            settings_data = api.notify_engine_active_setting_changed(
                engine_id, settings_data, setting_name, setting_value)
        [active_settings_item] = [
            item for item in settings_data.model['items']
            if item['caption'] == 'Active settings'
            ]
        stage_errors = _check_active_group_stage(
            expected_settings=actions['is_set'],
            actual_settings=settings_data.values,
            expected_model_data=actions['model_range'],
            actual_model_data=active_settings_item,
            )
        if stage_errors:
            errors[stage] = stage_errors
    return errors


def _check_active_group_for_agent(api, camera_id, engine_id, stages: Mapping):
    errors = {}
    agent_settings = api.get_device_analytics_settings(camera_id, engine_id)
    for stage, actions in stages.items():
        if actions['do_set']:
            [setting_name] = actions['do_set'].keys()
            [setting_value] = actions['do_set'].values()
            agent_settings = api.notify_device_active_setting_changed(
                camera_id, engine_id, agent_settings, setting_name, setting_value)
        [active_settings_section] = [
            item for item in agent_settings.model['sections']
            if item['caption'] == 'Active settings section'
            ]
        stage_errors = _check_active_group_stage(
            expected_settings=actions['is_set'],
            actual_settings=agent_settings.values,
            expected_model_data=actions['model_range'],
            actual_model_data=active_settings_section,
            )
        if stage_errors:
            errors[stage] = stage_errors
    return errors


def _check_active_button_for_engine(api, engine_id):
    user_input_text = 'User input for engine!'
    init_settings_data = api.get_analytics_engine_settings(engine_id)
    new_settings_data = api.notify_engine_active_setting_changed(
        engine_id=engine_id,
        engine_settings=init_settings_data,
        setting_name='showMessageButton',
        param_values={'parameter': user_input_text},
        )
    if user_input_text not in new_settings_data.message_to_user:
        return (
            f"Expected to find {user_input_text!r} in message to user. "
            f"Found {new_settings_data.message_to_user!r}")
    return None


def _check_active_button_for_agent(api, engine_id, camera_id):
    user_input_text = 'User input for agent!'
    init_settings_data = api.get_device_analytics_settings(camera_id, engine_id)
    new_settings_data = api.notify_device_active_setting_changed(
        camera_id=camera_id,
        engine_id=engine_id,
        agent_settings=init_settings_data,
        setting_name='showMessageButton',
        param_values={'parameter': user_input_text},
        )
    if user_input_text not in new_settings_data.message_to_user:
        return (
            f"Expected to find {user_input_text!r} in message to user. "
            f"Found {new_settings_data.message_to_user!r}")
    return None


def _test_stub_settings_active_settings(
        distrib_url: str,
        vm_type: str,
        api_version: str,
        exit_stack: ExitStack,
        with_plugins_from_release: Optional[str] = None,
        ):
    stand = prepare_one_mediaserver_stand(
        distrib_url, vm_type, api_version, exit_stack, with_plugins_from_release)
    ClassicInstallerSupplier(distrib_url).distrib().assert_not_older_than(
        'vms_5.1', "Active settings are supported starting from v.5.1")
    mediaserver = stand.mediaserver()
    recording_camera_id = exit_stack.enter_context(recording_camera(mediaserver)).id
    engine_collection = mediaserver.api.get_analytics_engine_collection()
    engine = engine_collection.get_stub('Settings')
    enable_device_agent(
        mediaserver.api, engine.name(), recording_camera_id)
    exit_stack.callback(
        check_for_plugin_diagnostic_events, mediaserver.api)
    errors = {}
    engine_button_error = _check_active_button_for_engine(mediaserver.api, engine.id())
    if engine_button_error is not None:
        errors.update({'engine_button': engine_button_error})
    engine_checkbox_errors = _check_active_setting_for_engine(
        mediaserver.api, engine.id(), _active_checkbox_stages)
    if engine_checkbox_errors:
        errors.update({'engine_checkbox': engine_checkbox_errors})
    engine_radiobutton_errors = _check_active_group_for_engine(
        mediaserver.api, engine.id(), _active_radiobutton_group_stages)
    if engine_radiobutton_errors:
        errors.update({'engine_radiobutton': engine_radiobutton_errors})
    engine_combobox_errors = _check_active_group_for_engine(
        mediaserver.api, engine.id(), _active_combobox_group_stages)
    if engine_combobox_errors:
        errors.update({'engine_combobox': engine_combobox_errors})
    agent_button_error = _check_active_button_for_agent(
        mediaserver.api, engine.id(), recording_camera_id)
    if agent_button_error is not None:
        errors.update({'agent_button': agent_button_error})
    agent_checkbox_errors = _check_active_setting_for_agent(
        mediaserver.api, recording_camera_id, engine.id(), _active_checkbox_stages)
    if agent_checkbox_errors:
        errors.update({'agent_checkbox': agent_checkbox_errors})
    agent_radiobutton_errors = _check_active_group_for_agent(
        mediaserver.api, recording_camera_id, engine.id(), _active_radiobutton_group_stages)
    if agent_radiobutton_errors:
        errors.update({'agent_radiobutton': agent_radiobutton_errors})
    agent_combobox_errors = _check_active_group_for_agent(
        mediaserver.api, recording_camera_id, engine.id(), _active_combobox_group_stages)
    if agent_combobox_errors:
        errors.update({'agent_combobox': agent_combobox_errors})
    assert not errors
