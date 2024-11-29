# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from threading import Thread
from typing import Callable

from websocket import WebSocket
from websocket import WebSocketConnectionClosedException
from websocket import WebSocketTimeoutException

_logger = logging.getLogger(__name__)


class _WebSocketClient:

    def __init__(self, ws: WebSocket):
        self._ws = ws
        self._received_message_callback = None
        self._listen_thread = Thread(target=self._listen, daemon=True)

    def send(self, message: str) -> None:
        _logger.debug("%r: sending: %s", self, message)
        if not self._ws.connected:
            raise RuntimeError(f"{self!r}: {self._ws!r} is not connected")
        self._ws.send(message)

    def _listen(self) -> None:
        _logger.info("%r: start listening for new messages", self)
        while True:
            try:
                raw_message = self._ws.recv()
            except WebSocketConnectionClosedException:
                _logger.info("%r: connection to remote host was lost", self)
                break
            except WebSocketTimeoutException:
                _logger.info("%r: connection timed out", self)
                break
            _logger.debug("%r: new message: %s", self, raw_message)
            self._received_message_callback(raw_message)
        _logger.info("%r: stopped listening for new messages", self)

    def start(self, received_message_callback: Callable[[str], None]) -> None:
        _logger.info("%r: starting", self)
        _logger.info(
            "%r: setting received message callback: %r", self, received_message_callback)
        self._received_message_callback = received_message_callback
        self._listen_thread.start()

    def stop(self) -> None:
        _logger.info("%r: please stop", self)
        self._listen_thread.join(timeout=self._ws.timeout + 2)
        _logger.info("%r: graciously stopped", self)

    def __repr__(self):
        return f"<{self.__class__.__name__}: websocket connected: {self._ws.connected}>"
