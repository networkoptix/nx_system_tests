# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import asyncio
import base64
import email
import json
import logging
import socket
import sys
import time
import unittest
from abc import ABCMeta
from abc import abstractmethod
from email.feedparser import FeedParser
from http import HTTPStatus
from mailbox import Message
from typing import Any
from typing import Callable
from typing import Coroutine
from typing import Generic
from typing import Mapping
from typing import Optional
from typing import TypeVar

from arms.mikrotik_power_control import MikrotikPowerControl
from arms.mikrotik_switch_api import MikrotikRESTApi


class _Session(metaclass=ABCMeta):

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self._reader = reader
        self._writer = writer

    @abstractmethod
    def close(self):
        pass

    @abstractmethod
    async def serve(self):
        pass


_T = TypeVar('_T', bound=_Session)


class SessionsServer(Generic[_T]):

    def __init__(self, server_socket: socket.socket):
        if server_socket.type != socket.SOCK_STREAM:
            raise RuntimeError(
                f"Protocol mismatch. Got: {server_socket.type}, Expected: {socket.SOCK_STREAM}")
        if server_socket.getblocking():
            raise RuntimeError("Server socket must be non-blocking")
        self._server_socket = server_socket
        self._active_sessions: dict[asyncio.Task, _T] = {}
        self._tcp_server: Optional[asyncio.Server] = None

    async def start_serving(
            self,
            sessions_factory: Callable[[asyncio.StreamReader, asyncio.StreamWriter], _T],
            ):
        self._tcp_server = await asyncio.start_server(
            client_connected_cb=lambda r, w: self._schedule_session(r, w, sessions_factory),
            sock=self._server_socket)
        await self._tcp_server.start_serving()

    def _schedule_session(
            self,
            reader: asyncio.StreamReader,
            writer: asyncio.StreamWriter,
            sessions_factory: Callable[[asyncio.StreamReader, asyncio.StreamWriter], _T],
            ):
        session = sessions_factory(reader, writer)
        task = asyncio.create_task(_client_session(writer, session.serve()))
        task.add_done_callback(self._finalizer)
        self._active_sessions[task] = session

    def _finalizer(self, task: asyncio.Task):
        session = self._active_sessions.pop(task)
        try:
            task.result()
        except Exception:
            logging.exception("%s done with exception", session)

    async def aclose(self):
        wait_exited = []
        if self._tcp_server is not None:
            self._tcp_server.close()
            wait_exited.append(self._tcp_server.wait_closed())
        wait_exited.extend(self._active_sessions.keys())
        for session in self._active_sessions.values():
            session.close()
        wait_timeout = 10
        await asyncio.wait_for(
            asyncio.gather(*wait_exited, return_exceptions=True), timeout=wait_timeout)
        _logger.info("Server is closed")

    def __repr__(self):
        listen_ip, listen_port = self._server_socket.getsockname()
        return f'<Server on {listen_ip}:{listen_port}>'


async def _client_session(writer: asyncio.StreamWriter, coro: Coroutine[Any, Any, Any]):
    try:
        await coro
    finally:
        writer.close()
        await writer.wait_closed()


class _MikrotikRestSession(_Session):

    _http_version = 'HTTP/1.0'

    def __init__(
            self,
            reader: asyncio.StreamReader,
            writer: asyncio.StreamWriter,
            switch: '_TestSwitch',
            auth_handler: '_AuthHandler',
            ):
        super().__init__(reader, writer)
        self._switch = switch
        self._auth_handler = auth_handler

    def close(self):
        self._writer.close()

    async def serve(self):
        try:
            await self._handle_single_request()
        except Exception:
            self._send_bad_request()
            raise

    async def _handle_single_request(self):
        request = await _Request.read_from(self._reader)
        body = await request.read_body(self._reader)
        try:
            self._auth_handler.handle(request)
        except _AuthorizationError:
            self._send_unauthorized()
            return
        if request.method == 'POST':
            self._handle_post(request, body)
        elif request.method == 'GET':
            if body:
                self._send_bad_request()
            else:
                self._handle_get(request)
        else:
            self._send_not_allowed()

    def _handle_get(self, request: '_Request'):
        if request.path.startswith('/rest/interface'):
            self._handle_port_status(request)
        else:
            self._send_not_found()

    def _handle_post(self, request: '_Request', body: bytes):
        if request.path == '/rest/interface/ethernet/poe/set':
            self._set_poe_status(body)
        else:
            self._send_not_found()

    def _handle_port_status(self, request: '_Request'):
        *_, port_name = request.path.rsplit('/', maxsplit=1)
        is_online = self._switch.is_online(port_name)
        status = "true" if is_online else "false"
        self._send_ok({'running': status})

    def _set_poe_status(self, body: bytes):
        data: Mapping[str, str] = json.loads(body)
        port_name = data['.id']
        requested_poe_status = data['poe-out']
        if requested_poe_status == 'off':
            self._switch.disable_poe(port_name)
        elif requested_poe_status == 'auto-on':
            self._switch.enable_poe(port_name)
        else:
            raise RuntimeError(f"Unexpected POE status {requested_poe_status}")
        self._send_ok([])

    def _send_not_allowed(self):
        code = HTTPStatus.METHOD_NOT_ALLOWED.value
        reason = HTTPStatus.METHOD_NOT_ALLOWED.phrase
        headers = Message()
        headers.add_header('Allow', 'GET, POST')
        self._send_status(code, reason, headers)

    def _send_bad_request(self):
        code = HTTPStatus.BAD_REQUEST.value
        reason = HTTPStatus.BAD_REQUEST.phrase
        self._send_status(code, reason, Message())

    def _send_unauthorized(self):
        code = HTTPStatus.UNAUTHORIZED.value
        reason = HTTPStatus.UNAUTHORIZED.phrase
        self._send_status(code, reason, Message())

    def _send_not_found(self):
        self._send_status(HTTPStatus.NOT_FOUND.value, HTTPStatus.NOT_FOUND.phrase, Message())

    def _send_ok(self, json_data: Any):
        response_body = json.dumps(json_data).encode('utf-8')
        headers = Message()
        headers.add_header('Content-Length', str(len(response_body)))
        headers.add_header('Content-Type', 'application/json')
        self._send_status(HTTPStatus.OK.value, HTTPStatus.OK.phrase, headers)
        self._writer.write(response_body)

    def _send_status(self, code: int, reason: str, headers: Message):
        buffer = bytearray()
        buffer.extend(f'{self._http_version} {code} {reason}\r\n'.encode('ascii'))
        buffer.extend(headers.as_bytes(policy=email.policy.HTTP))
        self._writer.write(buffer)

    def __repr__(self):
        return f'<REST: {id(self)}>'


class _TestSwitch:

    def __init__(self, ports: int, power_loss_delay: float):
        port_names = [f'ether{port_number}' for port_number in range(1, ports + 1)]
        self._ports = {port_name: _Port(port_name) for port_name in port_names}
        self._power_loss_delay = power_loss_delay
        self._repr = f"<SW-{ports}-{power_loss_delay}>"

    def enable_poe(self, port_name: str):
        self._ports[port_name].enable_poe()
        _logger.info("%s: ENABLED POE for port %s", self, port_name)

    def disable_poe(self, port_name: str):
        self._ports[port_name].disable_poe()
        _logger.info("%s: DISABLED POE for port %s", self, port_name)

    def is_online(self, port_name: str) -> bool:
        is_online = self._ports[port_name].is_online(self._power_loss_delay)
        status = "UP" if is_online else "DOWN"
        _logger.info("%s: Port %s is %s", self, port_name, status)
        return is_online

    def __repr__(self):
        return self._repr


class _Port:

    def __init__(self, name: str):
        self._name = name
        self._poe_is_enabled = False
        self._power_disabled_at = 0.0

    def enable_poe(self):
        self._poe_is_enabled = True

    def disable_poe(self):
        self._poe_is_enabled = False
        self._power_disabled_at = time.monotonic()

    def is_online(self, power_loss_delay: float) -> bool:
        if self._poe_is_enabled:
            return True
        power_loss_at = self._power_disabled_at + power_loss_delay
        if power_loss_at < time.monotonic():
            return False
        return True


class _Request:

    def __init__(self, method: str, path: str, protocol: str, headers: Message):
        self.method = method
        self.path = path
        self.protocol = protocol
        self.headers = headers

    @classmethod
    async def read_from(cls, reader: asyncio.StreamReader):
        request_line = await reader.readline()
        method, path, protocol = request_line.decode('ascii').split(maxsplit=2)
        headers = await _read_headers(reader)
        return cls(method, path, protocol, headers)

    async def read_body(self, reader: asyncio.StreamReader) -> bytes:
        body_length = int(self.headers.get('Content-Length', 0))
        if body_length > 0:
            return await reader.readexactly(body_length)
        return b''


async def _read_headers(reader: asyncio.StreamReader) -> Message:
    parser = FeedParser()
    while True:
        header_line = await reader.readline()
        if header_line == b'\r\n':
            break
        parser.feed(header_line.decode('ascii', errors='surrogateescape'))
    return parser.close()


class _AuthHandler(metaclass=ABCMeta):

    @abstractmethod
    def handle(self, request: _Request):
        pass


class _BasicAuthHandler(_AuthHandler):

    def __init__(self, username: str, password: str):
        self._username = username
        self._password = password
        result_string = base64.b64encode(f"{username}:{password}".encode("utf-8"))
        self._authorization = f"Basic {result_string.decode()}"

    def handle(self, request: _Request):
        if request.headers.get('Authorization', '') != self._authorization:
            raise _AuthorizationError()


class _AuthorizationError(Exception):
    pass


class _Status:

    def __init__(self, protocol: str, code: int, reason: str, headers: Message):
        self._protocol = protocol
        self._code = code
        self._reason = reason
        self._headers = headers

    def send(self, writer: asyncio.StreamWriter):
        buffer = bytearray()
        buffer.extend(f'{self._protocol} {self._code} {self._reason}'.encode('ascii'))
        buffer.extend(self._headers.as_bytes(policy=email.policy.HTTP))
        writer.write(buffer)


class TestMikrotik(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        server_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM)
        server_socket.setblocking(False)
        server_socket.bind(('127.0.0.2', 0))
        server_socket.listen(1)
        listen_ip, listen_port = server_socket.getsockname()
        username = 'irrelevant'
        password = 'irrelevant'
        self._correct_auth = _BasicAuthHandler(username, password)
        self._server_url = f'http://{username}:{password}@{listen_ip}:{listen_port}'
        _logger.info("Listen mock server on %s", self._server_url)
        self._mock_mikrotik_api = SessionsServer[_MikrotikRestSession](server_socket)
        self._test_switch = _TestSwitch(8, 3)

    async def asyncTearDown(self):
        await self._mock_mikrotik_api.aclose()

    async def test_wrong_auth(self):
        api = MikrotikRESTApi.from_url(self._server_url)
        irrelevant_port_number = 1
        power_control = MikrotikPowerControl(api, irrelevant_port_number)
        bad_auth_handler = _BasicAuthHandler("wrong_user", "wrong_password")
        await self._mock_mikrotik_api.start_serving(
            lambda r, w: _MikrotikRestSession(r, w, self._test_switch, bad_auth_handler))
        with self.assertRaisesRegex(RuntimeError, "credentials or the authorization method"):
            await power_control.power_off()

    async def test_power_off(self):
        api = MikrotikRESTApi.from_url(self._server_url)
        irrelevant_port_number = 1
        power_control = MikrotikPowerControl(api, irrelevant_port_number)
        await self._mock_mikrotik_api.start_serving(
            lambda r, w: _MikrotikRestSession(r, w, self._test_switch, self._correct_auth))
        await power_control.power_off()

    async def test_power_on(self):
        api = MikrotikRESTApi.from_url(self._server_url)
        irrelevant_port_number = 1
        power_control = MikrotikPowerControl(api, irrelevant_port_number)
        await self._mock_mikrotik_api.start_serving(
            lambda r, w: _MikrotikRestSession(r, w, self._test_switch, self._correct_auth))
        await power_control.power_on()

    async def test_power_off_fail(self):
        api = MikrotikRESTApi.from_url(self._server_url)
        irrelevant_port_number = 1
        power_control = MikrotikPowerControl(api, irrelevant_port_number)
        mock_switch = _TestSwitch(8, sys.maxsize)
        await self._mock_mikrotik_api.start_serving(
            lambda r, w: _MikrotikRestSession(r, w, mock_switch, self._correct_auth))
        with self.assertRaises(TimeoutError):
            await power_control.power_off()


_logger = logging.getLogger(__name__)

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)7s %(name)s %(message).5000s",
        )
    unittest.main()
