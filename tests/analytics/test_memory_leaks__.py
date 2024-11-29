# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import re
import time
from contextlib import ExitStack
from typing import Optional

from tests.analytics.common import check_for_plugin_diagnostic_events
from tests.analytics.common import enable_device_agent
from tests.analytics.common import prepare_one_mediaserver_stand
from tests.analytics.common import recording_camera
from tests.infra import Failure
from tests.waiting import WaitTimeout
from tests.waiting import wait_for_truthy

_logger = logging.getLogger(__name__)


def _test_memory_leaks_for_agents(
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
    errors_for_plugins = {}
    accumulated_error_log = ''
    ref_count_error_re = re.compile(
        r'RefCountableRegistry{.+}: The following \d+ objects remain registered:|'
        r'nx::sdk::analytics::ObjectMetadata{refCount: \d+, @(0x)?[0-9a-fA-F]+}')
    engine_collection = mediaserver.api.get_analytics_engine_collection()
    metadata_sdk_engines = [
        engine for engine in engine_collection.list_engines()
        if engine.name().startswith('Stub') or engine.name().startswith('Sample')]
    if not metadata_sdk_engines:
        raise Failure("No sample plugins included in Metadata SDK package were found")
    exit_stack.callback(
        check_for_plugin_diagnostic_events, mediaserver.api)
    for engine in metadata_sdk_engines:
        plugin_name = engine.name()
        _logger.info("Testing %s Device Agent for memory leaks", plugin_name)
        enable_device_agent(mediaserver.api, plugin_name, recording_camera_id)
        outgoing_metadata_log = _find_outgoing_metadata_log(
            mediaserver, engine.id(), recording_camera_id)
        try:
            wait_for_truthy(
                outgoing_metadata_log.read_text,
                description=f"{outgoing_metadata_log} is not empty")
        except WaitTimeout:
            _logger.warning(
                "Seems %s does not produce metadata stream; additional actions "
                "might be needed to induce the memory leak",
                plugin_name)
        # Make sure Device Agents are enabled one at a time
        mediaserver.api.disable_analytics_for_camera(recording_camera_id)
        mediaserver.stop()
        error_log = mediaserver.get_error_log()
        mediaserver.start()
        if len(accumulated_error_log) == len(error_log):
            _logger.info("No error logs found for Device Agent %s", plugin_name)
            continue
        new_error_log = error_log[len(accumulated_error_log):]
        accumulated_error_log = error_log
        _logger.warning(
            "Found error logs for Device Agent %s", plugin_name)
        ref_count_errors = ''
        for line in new_error_log.splitlines(keepends=True):
            if re.match(ref_count_error_re, line):
                ref_count_errors += line
        if not ref_count_errors:
            _logger.info(
                "No refCountableRegistry errors found in error log for Device Agent %s",
                plugin_name)
            continue
        _logger.warning(
            "Potential memory leak for Device Agent %s found, see log lines:\n%s",
            plugin_name, ref_count_errors)
        errors_for_plugins[plugin_name] = ref_count_errors
    assert not errors_for_plugins


def _find_outgoing_metadata_log(mediaserver, engine_id, camera_id):
    log_file_name = f'outgoing_metadata_device_{camera_id}_engine_{engine_id}.log'
    timeout_sec = 30
    started_at = time.monotonic()
    while True:
        try:
            [log_file] = mediaserver.list_log_files(mask=log_file_name)
            return log_file
        except ValueError:
            if time.monotonic() - started_at > timeout_sec:
                raise TimeoutError(f"No log file {log_file_name} found after {timeout_sec} sec")
            time.sleep(1)
