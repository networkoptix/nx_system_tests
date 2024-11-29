# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from queue import Queue
from typing import NamedTuple

import websocket

from mediaserver_api import MediaserverApi
from tests.analytics.metadata_api.integration._json_rpc import JsonRpcRequest
from tests.analytics.metadata_api.integration._json_rpc import _JsonRpcClient
from tests.analytics.metadata_api.integration._message_subscriber import _MessageSubscriber
from tests.analytics.metadata_api.integration._websocket_client import _WebSocketClient

_logger = logging.getLogger(__name__)


class MetadataApiIntegration:

    def __init__(self, api: MediaserverApi):
        self._api = api
        self._message_subscriber = _MessageSubscriber()
        self._ws = None
        self._ws_client = None
        self._json_rpc_client = None

    def __enter__(self):
        _logger.info("%r: set up started", self)
        websocket.enableTrace(True)
        self._ws = self._api.open_websocket('/jsonrpc', timeout_sec=3)
        self._ws_client = _WebSocketClient(self._ws)
        self._json_rpc_client = _JsonRpcClient(self._ws_client.send, self._message_subscriber.notify)
        self._ws_client.start(self._json_rpc_client.process_raw_message)
        _logger.info("%r: set up finished", self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        _logger.info("%r: stopping", self)
        self._ws.close()
        self._ws_client.stop()
        _logger.info("%r: stopped", self)

    def connect(self):
        self._json_rpc_client.send(
            JsonRpcRequest(
                method=_Methods.SUBSCRIBE,
                id_='connect',
                ))

    def subscribe_to_engine_active_settings_change(self) -> Queue:
        return self._message_subscriber.subscribe(_Methods.ENGINE_ACTIVE_SETTING_CHANGE)

    def __repr__(self):
        return (
            f"<{self.__class__.__name__} using {self._message_subscriber}, "
            f"{self._json_rpc_client} and {self._ws_client}>")


class _Methods(NamedTuple):

    SUBSCRIBE = 'rest.v4.analytics.subscribe'
    ENGINE_ACTIVE_SETTING_CHANGE = 'rest.v4.analytics.engines.settings.notifyActiveSettingChanged'
