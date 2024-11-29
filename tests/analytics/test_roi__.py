# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from contextlib import ExitStack
from typing import Optional

from tests.analytics.common import check_for_plugin_diagnostic_events
from tests.analytics.common import compare_settings_dicts
from tests.analytics.common import enable_device_agent
from tests.analytics.common import prepare_one_mediaserver_stand
from tests.analytics.common import recording_camera

_logger = logging.getLogger(__name__)


def _set_random_settings_for_stub_roi(api, camera_id, engine_id, seed: int = 0):
    new_settings = {
        'box1.figure': {
            'figure': {
                'color': f'#b2ff5{seed % 10}',
                'points': [
                    [1.0 / (2 + seed), 1.0 / (2 + seed)], [1.0 / (1 + seed), 1.0 / (1 + seed)]],
                },
            'label': f'Test label {seed}',
            'showOnCamera': [True, False][seed % 2],
            },
        'box1.minimumDuration': seed % 10,
        'box1.sensitivity': seed % 100 + 1,
        'box1.threshold': seed % 100 + 1,
        }
    _logger.info("Applying new Device Agent settings for \"Stub: ROI\"")
    api.set_device_analytics_settings(camera_id, engine_id, new_settings)
    return new_settings


def _list_stub_roi_agent_settings_errors(api, camera_id, engine_id, seed: int = 0):
    new_settings = _set_random_settings_for_stub_roi(api, camera_id, engine_id, seed)
    actual_settings = api.get_device_analytics_settings(camera_id, engine_id).values
    return compare_settings_dicts(new_settings, actual_settings)


def _test_stub_roi_agent_settings(
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
    engine = engine_collection.get_stub('ROI')
    enable_device_agent(
        mediaserver.api, engine.name(), recording_camera_id)
    exit_stack.callback(
        check_for_plugin_diagnostic_events, mediaserver.api)
    assert not _list_stub_roi_agent_settings_errors(
        mediaserver.api, recording_camera_id, engine.id())
