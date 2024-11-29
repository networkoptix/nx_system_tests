# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from contextlib import ExitStack
from typing import Optional

from mediaserver_api import EventType
from tests.analytics.common import add_analytics_event_rule
from tests.analytics.common import browse_for_event
from tests.analytics.common import check_for_plugin_diagnostic_events
from tests.analytics.common import enable_device_agent
from tests.analytics.common import prepare_one_mediaserver_stand
from tests.analytics.common import recording_camera


def _analytics_event_for_sample_occurred(api, event_resource_id, engine_id):
    caption_pattern = 'New sample plugin track started*'
    input_port_id = 'nx.sample.newTrack'
    add_analytics_event_rule(api, event_resource_id, engine_id, input_port_id)
    return browse_for_event(api, event_resource_id, caption_pattern, EventType.ANALYTICS_SDK)


def _test_analytics_event_from_sample_agent(
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
    engine = engine_collection.get_by_exact_name('Sample')
    enable_device_agent(
        mediaserver.api, engine.name(), recording_camera_id)
    exit_stack.callback(
        check_for_plugin_diagnostic_events, mediaserver.api)
    assert _analytics_event_for_sample_occurred(mediaserver.api, recording_camera_id, engine.id())
