# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
"""See: https://www.jsonrpc.org/specification."""

import json
import logging
from typing import Any
from typing import Callable
from typing import Hashable
from typing import Mapping
from typing import Optional
from typing import Union

_logger = logging.getLogger(__name__)


class JsonRpcRequest:

    def __init__(
            self,
            method: str,
            id_: Union[str, int],
            params: Optional[Mapping[str, Any]] = None,
            ):
        self.method = method
        self.id = id_
        self.params = params

    def as_str(self) -> str:
        data = {
            'jsonrpc': '2.0',
            'method': self.method,
            'id': self.id,
            }
        if self.params is not None:
            data['params'] = self.params
        return json.dumps(data)

    def __repr__(self):
        return (
            f"{self.__class__.__name__}(method={self.method}, id_={self.id}, params={self.params})")


class JsonRpcNotification:

    def __init__(self, method: str, params: Optional[Mapping[str, Any]] = None):
        self.method = method
        self.params = params

    def __repr__(self):
        return (
            f"{self.__class__.__name__}(method={self.method}, params={self.params})")


class JsonRpcResponse:

    def __init__(self, result, id_: Union[str, int]):
        self.result = result
        self.id = id_

    def as_str(self) -> str:
        return json.dumps({
            'jsonrpc': '2.0',
            'result': self.result,
            'id': self.id,
            })

    def __repr__(self):
        return f"{self.__class__.__name__}(id_={self.id}, result={self.result})"


class JsonRpcError(Exception):
    pass


class _JsonRpcClient:

    def __init__(
            self,
            send_message_callable: Callable[[str], None],
            received_message_callback: Callable[[Any, Hashable], None],
            ):
        self._send_message_callable = send_message_callable
        self._received_message_callback = received_message_callback

    def send(self, message: Union[JsonRpcRequest, JsonRpcResponse, JsonRpcNotification]) -> None:
        _logger.debug("%r: sending: %r", self, message)
        self._send_message_callable(message.as_str())

    def process_raw_message(self, raw: str) -> None:
        data = json.loads(raw)
        _logger.debug("%r: got raw message: %s", self, raw)
        if 'error' in data.keys():
            error_text = data['error']
            _logger.error("%r: error occurred: %s", self, error_text)
            raise JsonRpcError(error_text)
        if 'method' not in data.keys():
            message = JsonRpcResponse(data['result'], data['id'])
            self._received_message_callback(message, message.id)
        elif 'id' not in data.keys():
            message = JsonRpcNotification(data['method'], data.get('params'))
            self._received_message_callback(message, message.method)
        else:
            message = JsonRpcRequest(data['method'], data['id'], data.get('params'))
            # JSON-RPC protocol requires a response to a request message.
            self.send(JsonRpcResponse({}, message.id))
            self._received_message_callback(message, message.method)
            self._received_message_callback(message, message.id)
        _logger.debug("%r: parsed message: %r", self, message)
