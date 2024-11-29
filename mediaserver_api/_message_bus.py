# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import base64
import json
import logging
import re
import time
from functools import lru_cache
from typing import Any
from typing import Mapping
from typing import Optional

from websocket import WebSocketException
from websocket import WebSocketTimeoutException

from mediaserver_api._mediaserver import MediaserverApi
from mediaserver_api._mediaserver_v0 import MediaserverApiV0

_logger = logging.getLogger(__name__)


def wait_until_no_transactions(
        mediaserver_api: MediaserverApi,
        silence_sec: float,
        timeout_sec: float,
        ):
    transaction_socket = TransactionBusSocket(mediaserver_api)
    last_transaction_received = time.monotonic()
    started_at = time.monotonic()
    while True:
        try:
            transaction = transaction_socket.get_transaction()
        except TransactionBusSocketError as e:
            _logger.debug("Error on receiving transaction: %s", e)
            transaction_socket.reset()
            last_transaction_received = time.monotonic()
        else:
            if transaction is not None:
                _logger.debug("Received transaction %s", transaction.get_command())
                last_transaction_received = time.monotonic()
            else:
                _logger.debug("No transaction received")
        if time.monotonic() - last_transaction_received > silence_sec:
            _logger.debug("No transactions for %.2f seconds", silence_sec)
            break
        if time.monotonic() - started_at > timeout_sec:
            raise RuntimeError(f"Timed out waiting for no transactions for {timeout_sec} seconds")


class TransactionBusSocket:

    def __init__(self, mediaserver_api: MediaserverApi):
        self._api = mediaserver_api
        self._timeout_sec = 0.5
        self._websocket = self._create_websocket()

    def _create_websocket(self):
        if not isinstance(self._api, MediaserverApiV0):
            self._api.refresh_session()
        return self._api.open_transaction_bus_websocket(timeout_sec=self._timeout_sec)

    def get_transaction(self) -> Optional['Transaction']:
        try:
            raw_transaction = self._websocket.recv()
        except WebSocketTimeoutException:
            return None
        except (WebSocketException, ConnectionError) as e:
            raise TransactionBusSocketError(str(e))
        return Transaction(raw_transaction)

    def reset(self):
        self._websocket.close()
        self._websocket = self._create_websocket()


class Transaction:

    def __init__(self, raw_transaction: str):
        self._raw = raw_transaction

    @lru_cache(1)
    def get_command(self) -> str:
        # json.loads takes significant time to parse getFullInfo transaction (3-4 ms).
        # With large number of transactions this will impact performance and measurement accuracy.
        # To speed up process perform full parsing only when necessary and extract command with
        # regex.
        match = re.match(r'{"tran":{"command":"(?P<command>\w+)",', self._raw)
        if match is None:
            raise RuntimeError(f"Failed to extract command from{self._raw}")
        return match.group('command')

    @lru_cache(1)
    def _parse(self) -> Mapping[str, Any]:
        return json.loads(self._raw)

    @lru_cache(1)
    def get_caption(self) -> Optional[str]:
        parsed_transaction = self._parse()
        _logger.debug("Parsed transaction: %s", parsed_transaction)
        params = parsed_transaction['tran'].get('params', {})
        runtime_params_raw = params.get('runtimeParams')
        if runtime_params_raw is None:
            _logger.debug("'runtimeParams' field is absent")
            return None
        runtime_params = json.loads(base64.b64decode(runtime_params_raw))
        transaction_id_field = 'caption'
        received_transaction_id = runtime_params.get(transaction_id_field)
        if received_transaction_id is None:
            _logger.debug("%r field is absent", transaction_id_field)
            return None
        return received_transaction_id


class TransactionBusSocketError(Exception):
    pass
