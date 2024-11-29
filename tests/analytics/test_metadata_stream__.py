# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from contextlib import ExitStack
from typing import Optional

from installation import ClassicInstallerSupplier
from tests.analytics.common import check_for_plugin_diagnostic_events
from tests.analytics.common import enable_device_agent
from tests.analytics.common import live_metadata_stream_errors
from tests.analytics.common import prepare_one_mediaserver_stand
from tests.analytics.common import recording_camera
from tests.analytics.common import set_object_streamer_tracks


def _test_live_metadata_stream(
        distrib_url: str,
        vm_type: str,
        api_version: str,
        stream: str,
        exit_stack: ExitStack,
        with_plugins_from_release: Optional[str] = None,
        ):
    stand = prepare_one_mediaserver_stand(
        distrib_url, vm_type, api_version, exit_stack, with_plugins_from_release)
    newer_than_5_1 = ClassicInstallerSupplier(distrib_url).distrib().newer_than('vms_5.1')
    mediaserver = stand.mediaserver()
    recording_camera_id = exit_stack.enter_context(recording_camera(mediaserver)).id
    if newer_than_5_1:
        engine_id = _set_up_object_streamer_plugin(mediaserver, recording_camera_id)
    else:
        engine_id = _set_up_object_detection_plugin(mediaserver, recording_camera_id)
    exit_stack.callback(
        check_for_plugin_diagnostic_events, mediaserver.api)
    assert not live_metadata_stream_errors(
        mediaserver,
        engine_id,
        recording_camera_id,
        stream,
        )


def _set_up_object_streamer_plugin(mediaserver, camera_id):
    set_object_streamer_tracks(mediaserver, camera_id, skip_service_tracks=True)
    engine_collection = mediaserver.api.get_analytics_engine_collection()
    engine = engine_collection.get_stub('Object Streamer')
    enable_device_agent(
        mediaserver.api, engine.name(), camera_id)
    return engine.id()


def _set_up_object_detection_plugin(mediaserver, camera_id):
    engine_collection = mediaserver.api.get_analytics_engine_collection()
    engine = engine_collection.get_stub('Object Detection')
    enable_device_agent(
        mediaserver.api, engine.name(), camera_id)
    return engine.id()
