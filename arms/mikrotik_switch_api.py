# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
# REST documentation
# See: https://help.mikrotik.com/docs/display/ROS/REST+API
import asyncio
import base64
import copy
import email.policy
import json
import logging
from abc import ABCMeta
from abc import abstractmethod
from contextlib import asynccontextmanager
from email.message import Message
from email.parser import FeedParser
from http import HTTPStatus
from http.client import HTTPException
from typing import Any
from typing import AsyncContextManager
from typing import Mapping
from typing import Optional
from typing import Sequence
from typing import Union
from urllib.parse import urlparse


class MikrotikRESTApi:

    @classmethod
    def from_url(cls, url: str) -> 'MikrotikRESTApi':
        parsed = urlparse(url)
        if parsed.scheme == 'http':
            port = parsed.port or 80
            use_tls = False
        elif parsed.scheme == 'https':
            port = parsed.port or 443
            use_tls = True
        else:
            raise RuntimeError(f"Unsupported scheme {parsed.scheme}")
        if None in (parsed.password, parsed.username):
            raise RuntimeError("Credentials must be provided")
        auth_handler = _BasicAuthHandler(parsed.username, parsed.password)
        return cls(parsed.hostname, port, auth_handler, use_tls)

    def __init__(self, hostname: str, port: int, auth_handler: '_AuthHandler', use_tls: bool):
        self._hostname = hostname
        self._use_tls = use_tls
        self._port = port
        self._auth_handler = auth_handler

    async def post(
            self,
            path: str,
            json_data: Mapping[str, Any]) -> Union[Mapping[Any, Any], Sequence[Any]]:
        json_encoded = json.dumps(json_data).encode('utf-8')
        request = self._build_authorized_request('POST', path)
        request = request.with_header('Content-Type', 'application/json')
        request_with_length = request.with_header('Content-Length', str(len(json_encoded)))
        async with self._stream() as (reader, writer):  # type: asyncio.StreamReader, asyncio.StreamWriter
            _logger.debug("Send %s", request_with_length)
            request_with_length.send(writer, 'HTTP/1.0')
            _logger.debug("Send body: %s", json_encoded)
            writer.write(json_encoded)
            response = await _HTTPResponse.read_from(reader)
            if response.status.protocol != 'HTTP/1.0':
                raise RuntimeError(f"Unsupported protocol received: {response.status.protocol}")
            if response.status.code == HTTPStatus.UNAUTHORIZED:
                self._auth_handler.handle_unauthorized(request)
            response.try_raise()
            response_body = await response.read_body(reader)
            _logger.debug("Received body: %s", response_body)
            return json.loads(response_body)

    async def get(self, path: str) -> Union[Mapping[Any, Any], Sequence[Any]]:
        request = self._build_authorized_request('GET', path)
        async with self._stream() as (reader, writer):  # type: asyncio.StreamReader, asyncio.StreamWriter
            _logger.debug("Send %s", request)
            request.send(writer, 'HTTP/1.0')
            response = await _HTTPResponse.read_from(reader)
            if response.status.protocol != 'HTTP/1.0':
                raise RuntimeError(f"Unsupported protocol received: {response.status.protocol}")
            if response.status.code == HTTPStatus.UNAUTHORIZED:
                self._auth_handler.handle_unauthorized(request)
            response.try_raise()
            response_body = await response.read_body(reader)
            _logger.debug("Received body: %s", response_body)
            return json.loads(response_body)

    def _build_authorized_request(self, method: str, path: str) -> '_HTTPRequest':
        request = _HTTPRequest(method, '/rest/' + path.lstrip("/"))
        request = request.with_header('User-Agent', 'FTHTTPClient')
        request = request.with_header('Accept', '*/*')
        request = self._auth_handler.with_auth_info(request)
        return request

    @asynccontextmanager
    async def _stream(self) -> AsyncContextManager[tuple[asyncio.StreamReader, asyncio.StreamWriter]]:
        reader, writer = await asyncio.open_connection(
            self._hostname, self._port, ssl=self._use_tls)
        try:
            yield reader, writer
        finally:
            writer.close()
            await writer.wait_closed()


class _AuthHandler(metaclass=ABCMeta):

    @abstractmethod
    def handle_unauthorized(self, request: '_HTTPRequest'):
        pass

    @abstractmethod
    def with_auth_info(self, request: '_HTTPRequest') -> '_HTTPRequest':
        pass


class _BasicAuthHandler(_AuthHandler):

    def __init__(self, username: str, password: str):
        self._user = username
        result_string = base64.b64encode(f"{username}:{password}".encode("utf-8"))
        self._authorization = f"Basic {result_string.decode()}"

    def handle_unauthorized(self, request: '_HTTPRequest'):
        if request.get_header('Authorization') == self._authorization:
            raise RuntimeError(
                f"{request} contains proper authorization for user {self._user}. "
                f"Either credentials or the authorization method are incorrect")
        raise RuntimeError(f"{request} does not contain authorization for user {self._user}")

    def with_auth_info(self, request: '_HTTPRequest') -> '_HTTPRequest':
        return request.with_header('Authorization', self._authorization)


class _HTTPRequest:

    def __init__(self, method: str, path: str):
        self._method = method
        self._path = path
        self._headers = Message()

    def _copy(self) -> '_HTTPRequest':
        new_request = _HTTPRequest(self._method, self._path)
        new_request._headers = copy.deepcopy(self._headers)
        return new_request

    def with_header(self, key: str, value: str) -> '_HTTPRequest':
        new_request = self._copy()
        try:
            new_request._headers.replace_header(key, value)
        except KeyError:
            new_request._headers.add_header(key, value)
        return new_request

    def get_header(self, name: str) -> Optional[str]:
        return self._headers.get(name)

    def send(self, writer: asyncio.StreamWriter, protocol: str):
        send_buffer = bytearray(f'{self._method} {self._path} {protocol}\r\n'.encode('ascii'))
        send_buffer.extend(self._headers.as_bytes(policy=email.policy.HTTP))
        writer.write(send_buffer)

    def __repr__(self):
        return f'<{self._method}: {self._path}, {self._headers}>'


class _HTTPResponse:

    def __init__(self, status: '_HTTPStatus', headers: Message):
        self.status = status
        self.headers = headers

    def try_raise(self):
        if 200 <= self.status.code <= 299:
            return
        raise HTTPException(
            f"Code {self.status.code}: {self.status.reason}. Headers: {self.headers}")

    @classmethod
    async def read_from(cls, reader: asyncio.StreamReader):
        status = await _HTTPStatus.read(reader)
        headers = await _read_headers(reader)
        return cls(status, headers)

    async def read_body(self, reader: asyncio.StreamReader) -> bytes:
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length > 0:
            return await reader.readexactly(content_length)
        return b''


class _HTTPStatus:

    def __init__(self, protocol: str, code: int, reason: str):
        self.protocol = protocol
        self.code = code
        self.reason = reason

    @classmethod
    async def read(cls, reader: asyncio.StreamReader):
        status_line = await reader.readline()
        protocol, code, reason = status_line.strip().decode().split(maxsplit=2)
        return cls(protocol, int(code), reason)


async def _read_headers(reader: asyncio.StreamReader) -> Message:
    parser = FeedParser()
    while True:
        header_line = await reader.readline()
        if header_line == b'\r\n':
            break
        parser.feed(header_line.decode('ascii', errors='surrogateescape'))
    return parser.close()


_logger = logging.getLogger(__name__)
