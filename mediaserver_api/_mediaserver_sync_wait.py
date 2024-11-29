# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
"""Wait for mediaservers to synchronize between themselves."""
import json
import logging
import time

from mediaserver_api._diff_schemes import transaction_log_differ
from mediaserver_api._mediaserver import log_full_info_diff
from mediaserver_api._message_bus import wait_until_no_transactions

_logger = logging.getLogger(__name__)

MEDIASERVER_MERGE_TIMEOUT_SEC: float = 5 * 60


def _servers_info_synced(servers):
    [first_server, *other_servers] = servers
    first_server_info = first_server.api.get_full_info()
    for other_server in other_servers:
        other_server_info = other_server.api.get_full_info()
        diff_list = first_server_info.diff(other_server_info)
        if diff_list:
            _logger.info("Full info from %r and %r are different", first_server, other_server)
            log_full_info_diff(_logger.debug, diff_list)
            return False
    return True


def wait_for_servers_info_synced(servers, timeout_sec=MEDIASERVER_MERGE_TIMEOUT_SEC):
    started_at = time.monotonic()
    while True:
        if _servers_info_synced(servers):
            return
        if time.monotonic() - started_at > timeout_sec:
            raise RuntimeError(f"Servers information did not sync in {timeout_sec} seconds")
        _logger.info("Waiting for servers information synced")
        time.sleep(1)


def _save_json_artifact(artifacts_dir, name, data):
    file_path = artifacts_dir.joinpath(name).with_suffix('.json')
    file_path.write_text(json.dumps(data, indent=4))


def _wait_for_transaction_logs_synced(servers, timeout_sec, artifacts_dir):
    [first_server, *other_servers] = servers
    started_at = time.monotonic()
    while True:
        first_server_logs = first_server.api.get_transaction_log()
        for other_server in other_servers:
            other_server_logs = other_server.api.get_transaction_log()
            diff_list = transaction_log_differ.diff(first_server_logs, other_server_logs)
            if diff_list:
                _logger.info(
                    "Transaction logs from %r and %r are different",
                    first_server,
                    other_server,
                    )
                for log_line in diff_list:
                    _logger.debug(log_line)
                break
        else:
            break
        if time.monotonic() - started_at < timeout_sec:
            _logger.info("Waiting for transaction logs synchronization")
            time.sleep(1)
            continue
        first_server_name = first_server.api.get_server_name()
        _save_json_artifact(
            artifacts_dir,
            f'transaction_logs-{first_server_name}',
            first_server_logs,
            )
        other_server_name = other_server.api.get_server_name()
        _save_json_artifact(
            artifacts_dir,
            f'transaction_logs-{other_server_name}',
            other_server_logs,
            )
        raise RuntimeError(f"Transaction logs did not sync in {timeout_sec} seconds")


def wait_for_servers_synced(artifacts_dir, server_list):
    start_time = time.monotonic()

    def timeout_left_sec():
        return MEDIASERVER_MERGE_TIMEOUT_SEC - (time.monotonic() - start_time)

    [_, mediaserver, *_] = server_list
    wait_until_no_transactions(mediaserver.api, silence_sec=3, timeout_sec=timeout_left_sec())
    wait_for_servers_info_synced(server_list, timeout_sec=timeout_left_sec())
    _wait_for_transaction_logs_synced(server_list, timeout_left_sec(), artifacts_dir)
