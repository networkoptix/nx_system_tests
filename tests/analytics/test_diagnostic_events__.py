# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from contextlib import ExitStack
from typing import Optional

from mediaserver_api import EventType
from tests.analytics.common import attribute_names
from tests.analytics.common import browse_for_event
from tests.analytics.common import check_for_plugin_diagnostic_events
from tests.analytics.common import enable_device_agent
from tests.analytics.common import prepare_one_mediaserver_stand
from tests.analytics.common import recording_camera


def _diagnostic_event_from_engine_occurred(api, engine_id, settings_flag_names):
    api.set_analytics_engine_settings(
        engine_id,
        {name: True for name in settings_flag_names},
        )
    return browse_for_event(
        api,
        engine_id,
        '*message from Engine',
        EventType.PLUGIN_DIAGNOSTIC_EVENT,
        )


def _diagnostic_event_from_agent_occurred(api, camera_id, engine_id, settings_flag_names):
    api.set_device_analytics_settings(
        camera_id,
        engine_id,
        {name: True for name in settings_flag_names},
        )
    return browse_for_event(
        api,
        engine_id,
        '*message from DeviceAgent',
        EventType.PLUGIN_DIAGNOSTIC_EVENT,
        )


def _test_diagnostic_event_from_stub(
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
    engine_collection = mediaserver.api.get_analytics_engine_collection()
    engine = engine_collection.get_stub(
        'Plugin Diagnostic Events', 'Integration Diagnostic Events')
    enable_device_agent(
        mediaserver.api, engine.name(), recording_camera_id)
    exit_stack.callback(
        check_for_plugin_diagnostic_events, mediaserver.api)
    engine_event_occurred = _diagnostic_event_from_engine_occurred(
        mediaserver.api, engine.id(), attribute_names.diagnostic_event_flags_for_engine)
    agent_event_occurred = _diagnostic_event_from_agent_occurred(
        mediaserver.api, recording_camera_id, engine.id(),
        attribute_names.diagnostic_event_flags_for_agent,
        )
    assert engine_event_occurred and agent_event_occurred, (
        f"Engine event occurred: {engine_event_occurred}, "
        f"Device Agent event occurred: {agent_event_occurred}. "
        "Expected both to be True.")
