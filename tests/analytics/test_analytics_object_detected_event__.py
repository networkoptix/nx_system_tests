# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from contextlib import ExitStack
from typing import Optional

from mediaserver_api import EventType
from tests.analytics.common import add_analytics_event_rule
from tests.analytics.common import browse_for_event
from tests.analytics.common import check_for_plugin_diagnostic_events
from tests.analytics.common import enable_device_agent
from tests.analytics.common import prepare_one_mediaserver_stand
from tests.analytics.common import recording_camera

_logger = logging.getLogger(__name__)


def _test_analytics_object_detected_event(
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
    engine = engine_collection.get_stub('Object Detection')
    engine_name = engine.name()
    enable_device_agent(mediaserver.api, engine_name, recording_camera_id)
    exit_stack.callback(
        check_for_plugin_diagnostic_events, mediaserver.api)
    object_type_id = 'nx.base.Dog'
    _logger.info(
        "Enable generation of object with type ID %s for Device Agent %s on camera %s",
        object_type_id, engine_name, recording_camera_id,
        )
    mediaserver.api.set_device_analytics_settings(
        device_id=recording_camera_id,
        engine_id=engine.id(),
        settings_values={f'objectTypeIdToGenerate.{object_type_id}': True},
        )
    event_type = EventType.ANALYTICS_OBJECT_DETECTED
    _logger.info(
        "Add event rule with inputPortId %s and eventType %s for Device Agent %s on camera %s",
        object_type_id, event_type, engine_name, recording_camera_id,
        )
    add_analytics_event_rule(
        api=mediaserver.api,
        resource_id=recording_camera_id,
        engine_id=engine.id(),
        input_port_id=object_type_id,
        event_type=event_type,
        )
    _logger.info(
        "Browse for events from camera %s with eventType %s", recording_camera_id, event_type)
    assert browse_for_event(
        api=mediaserver.api,
        resource_id=recording_camera_id,
        caption_pattern='*',
        event_type=event_type,
        )
