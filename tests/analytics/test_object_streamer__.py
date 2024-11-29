# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time
from contextlib import ExitStack
from typing import Optional

from mediaserver_api import TimePeriod
from tests.analytics.common import check_for_plugin_diagnostic_events
from tests.analytics.common import enable_device_agent
from tests.analytics.common import prepare_one_mediaserver_stand
from tests.analytics.common import recording_camera

_logger = logging.getLogger(__name__)


def _test_recorded_time_periods(
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
    first_period_duration_s = 30
    gap_duration_s = 15
    second_period_duration_s = 20
    # Determined experimentally: up to 6s (platform-dependent) to enable/disable Device Agent
    abs_tolerance_ms = 7000
    # The Desktop Client uses a detail level of 1000ms, but on tests, due to the high load on the
    # test servers, it may not be enough, so 1500ms is used.
    # If periods are closer than detail_level_ms to each
    # other these periods "stick" together and returned to the client as one big period
    detail_level_ms = 1500
    api = mediaserver.api
    engine_collection = api.get_analytics_engine_collection()
    engine = engine_collection.get_stub('Object Streamer')
    engine_name = engine.name()
    _logger.info("Enable %s Device Agent", engine_name)
    enable_device_agent(api, engine_name, recording_camera_id)
    exit_stack.callback(
        check_for_plugin_diagnostic_events, mediaserver.api)
    # Enabling Device Agent takes time so start time has to be measured after it was enabled
    first_period_start = mediaserver.os_access.get_datetime()
    _logger.info(
        "Wait for %ds to record first portion of analytics metadata", first_period_duration_s)
    time.sleep(first_period_duration_s)
    api.disable_device_agents(recording_camera_id)
    # Disabling Device Agent takes time, so we can't just add expected period length to start time
    # to get the end time of the period
    first_period_end = mediaserver.os_access.get_datetime()
    _logger.info("Wait for %ds to make a gap between recorded periods", gap_duration_s)
    time.sleep(gap_duration_s)
    _logger.info("Enable %s Device Agent", engine_name)
    enable_device_agent(api, engine_name, recording_camera_id)
    second_period_start = mediaserver.os_access.get_datetime()
    _logger.info(
        "Wait for %ds to record second portion of analytics metadata", second_period_duration_s)
    time.sleep(second_period_duration_s)
    api.disable_device_agents(recording_camera_id)
    second_period_end = mediaserver.os_access.get_datetime()
    [periods] = api.list_recorded_periods(
        camera_ids=[recording_camera_id],
        periods_type=api.RecordedPeriodsType.ANALYTICS,
        detail_level_ms=detail_level_ms,
        )
    assert len(periods) == 2
    [first_period, second_period] = periods
    first_period_expected = TimePeriod.from_datetime(
        start=first_period_start,
        duration=first_period_end - first_period_start,
        )
    first_period_is_ok = first_period_expected.contains(
        first_period.trim_left(abs_tolerance_ms).trim_right(abs_tolerance_ms))
    second_period_expected = TimePeriod.from_datetime(
        start=second_period_start,
        duration=second_period_end - second_period_start,
        )
    second_period_is_ok = second_period_expected.contains(
        second_period.trim_left(abs_tolerance_ms).trim_right(abs_tolerance_ms))
    errors = []
    if not first_period_is_ok:
        errors.append(
            f"Period 1 expected to be equal to {first_period_expected} with abs tolerance "
            f"{abs_tolerance_ms}ms; actual is {first_period}")
    if not second_period_is_ok:
        errors.append(
            f"Period 2 expected to be equal to {second_period_expected} with abs tolerance "
            f"{abs_tolerance_ms}ms; actual is {second_period}")
    assert not errors
