# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from contextlib import ExitStack
from typing import Optional
from uuid import UUID

from mediaserver_api import EventType
from mediaserver_api import MediaserverApi
from tests.analytics.common import add_analytics_event_rule
from tests.analytics.common import browse_for_event
from tests.analytics.common import check_for_plugin_diagnostic_events
from tests.analytics.common import enable_device_agent
from tests.analytics.common import list_events
from tests.analytics.common import prepare_one_mediaserver_stand
from tests.analytics.common import recording_camera


def _analytics_event_occurred(
        api: MediaserverApi,
        camera_id: UUID,
        engine_id: UUID,
        caption_pattern: str,
        event_subtype_id: str,
        ) -> bool:
    add_analytics_event_rule(api, camera_id, engine_id, event_subtype_id)
    return browse_for_event(
        api=api,
        resource_id=camera_id,
        caption_pattern=caption_pattern,
        event_type=EventType.ANALYTICS_SDK,
        event_subtype=event_subtype_id,
        )


class _StubAnalyticsEventSubtypes:

    LINE_CROSSING = 'nx.stub.lineCrossing'
    OBJECT_IN_AREA = 'nx.stub.objectInTheArea'


def line_crossing_event_occurred(
        api: MediaserverApi,
        camera_id: UUID,
        engine_id: UUID,
        ) -> bool:
    caption_pattern = 'Line crossing - impulse event (caption)'
    return _analytics_event_occurred(
        api, camera_id, engine_id, caption_pattern, _StubAnalyticsEventSubtypes.LINE_CROSSING)


def object_in_the_area_event_occurred(
        api: MediaserverApi,
        camera_id: UUID,
        engine_id: UUID,
        ) -> bool:
    caption_pattern = 'Object in the Area - prolonged event (caption)*'
    return _analytics_event_occurred(
        api, camera_id, engine_id, caption_pattern, _StubAnalyticsEventSubtypes.OBJECT_IN_AREA)


def _test_analytics_event_from_stub_agent(
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
    engine = engine_collection.get_stub('Events')
    enable_device_agent(
        mediaserver.api, engine.name(), recording_camera_id)
    exit_stack.callback(
        check_for_plugin_diagnostic_events, mediaserver.api)
    assert line_crossing_event_occurred(
        mediaserver.api, recording_camera_id, engine.id())
    assert object_in_the_area_event_occurred(
        mediaserver.api, recording_camera_id, engine.id())
    # Check that events of both subtypes are fetched when no subtype filter is provided
    all_analytics_events = list_events(
        api=mediaserver.api,
        camera_id=recording_camera_id,
        event_type=EventType.ANALYTICS_SDK,
        )
    assert any([
        event.match(event_subtype=_StubAnalyticsEventSubtypes.LINE_CROSSING)
        for event in all_analytics_events])
    assert any([
        event.match(event_subtype=_StubAnalyticsEventSubtypes.OBJECT_IN_AREA)
        for event in all_analytics_events])
