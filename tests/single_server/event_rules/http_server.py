# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import socket
from contextlib import AbstractContextManager
from contextlib import contextmanager
from email.parser import FeedParser
from typing import Any
from typing import BinaryIO
from typing import Final
from typing import Mapping
from typing import Optional

_logger = logging.getLogger(__name__)


class HttpRequest:

    def __init__(self, stream: BinaryIO):
        self.status_line = stream.readline().strip().decode('ascii')
        [self.method, self._uri, _] = self.status_line.split(maxsplit=2)
        self._query = ''
        if '?' in self._uri:
            [self._uri, self._query] = self._uri.split('?', 1)
        headers_raw = b''.join(iter(stream.readline, b'\r\n'))
        parser = FeedParser()
        parser.feed(headers_raw.decode('ascii', errors='surrogateescape'))
        self._headers = parser.close()
        self.text = ''
        content_length = int(self._headers.get('Content-Length', 0))
        if content_length > 0:
            data = stream.read(content_length)
            read_content_length = len(data)
            if read_content_length != content_length:
                raise RuntimeError(
                    f"Content-Length is {content_length} but received {read_content_length} bytes")
            self.text = data.decode('utf8')
        self._stream = stream

    def header(self, key: str) -> Any:
        return self._headers[key]

    def respond(self, respond_str: str, respond_headers: Optional[Mapping] = None):
        request_line = f'HTTP/1.0 {respond_str}'
        self._stream.write(f'{request_line}\r\n'.encode('ascii'))
        _logger.info("Send request line: %s", request_line)
        if respond_headers:
            for [field_name, field_value] in respond_headers.items():
                header = f'{field_name}: {field_value}\r\n'
                self._stream.write(header.encode('ascii'))
                _logger.info("Send header: %s", header)
        self._stream.write(b'\r\n')
        self._stream.flush()


class HttpServer:
    _timeout_sec: Final = 5

    def __init__(self, sock: socket.socket):
        self._server_socket = sock
        self._server_socket.settimeout(self._timeout_sec)
        self.port = int(self._server_socket.getsockname()[1])

    @contextmanager
    def wait(self) -> AbstractContextManager[HttpRequest]:
        [client_socket, address] = self._server_socket.accept()
        _logger.info("Accept connection from %s", address)
        with client_socket:
            client_socket.settimeout(self._timeout_sec)
            with client_socket.makefile('rwb') as stream:
                yield HttpRequest(stream)
