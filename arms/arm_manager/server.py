# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import asyncio
import logging
import socket
from abc import ABCMeta
from abc import abstractmethod
from collections.abc import Mapping
from collections.abc import Sequence
from contextlib import closing
from typing import Any
from typing import AsyncGenerator
from typing import Callable
from typing import Generic
from typing import Set
from typing import TypeVar

from arms.arm_manager.protocol import Ack
from arms.arm_manager.protocol import CommitSnapshotRequest
from arms.arm_manager.protocol import Error
from arms.arm_manager.protocol import Greet
from arms.arm_manager.protocol import LockedMachineClientInfo
from arms.arm_manager.protocol import Nok
from arms.arm_manager.protocol import Ok
from arms.arm_manager.protocol import ReleaseMachineRequest
from arms.arm_manager.protocol import RequestMsg
from arms.arm_manager.protocol import RequestType
from arms.arm_manager.protocol import StatusMsg
from arms.market import CommandFailed
from arms.market import ContractRejected
from arms.market import ContractorQuit
from arms.market import Market
from arms.market import SignedContract

_logger = logging.getLogger(__name__.split('.')[-1])

_EOL = b"\r\n"


def bind_server_socket(listen_host: str, listen_port: int) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)

    # TCP Keepalive https://datatracker.ietf.org/doc/html/rfc1122#page-101
    # is always enabled and set to minimum intervals
    # to provide a reliable mechanism of session tracking
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, True)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 1)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 1)

    sock.bind((listen_host, listen_port))
    sock.setblocking(False)
    _logger.info("TCP Server is opened on %s:%s", listen_host, listen_port)
    return sock


class _ConcurrentSession(metaclass=ABCMeta):

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        peername = writer.get_extra_info('peername')
        if peername is None:
            RuntimeError("peername should not be None")
        peer_ip, peer_port = peername
        self._peername = f"{peer_ip}:{peer_port}"
        self._reader = reader
        self._writer = writer
        self._task = asyncio.create_task(self._serve(), name=self._peername)

    def get_exception(self):
        return self._task.exception()

    def add_done_callback(self, callback: Callable[['_ConcurrentSession'], None]):
        self._task.add_done_callback(lambda task: callback(self))

    @abstractmethod
    async def _serve(self):
        pass

    @abstractmethod
    def close(self):
        pass

    @abstractmethod
    async def wait_closed(self):
        pass


_T = TypeVar('_T', bound=type[_ConcurrentSession])


class SessionsServer(Generic[_T]):

    def __init__(self, server_socket: socket.socket):
        if server_socket.type != socket.SOCK_STREAM:
            raise RuntimeError(
                f"Protocol mismatch. Got: {server_socket.type}, Expected: {socket.SOCK_STREAM}")
        if server_socket.getblocking():
            raise RuntimeError("Server socket must be non-blocking")
        self._server_socket = server_socket
        self._sessions: Set[_ConcurrentSession] = set()
        self._tcp_server = None

    async def serve(
            self,
            sessions_factory: Callable[[asyncio.StreamReader, asyncio.StreamWriter], _T],
            ):
        self._tcp_server = await asyncio.start_server(
            client_connected_cb=lambda r, w: self._schedule_session(r, w, sessions_factory),
            sock=self._server_socket)
        async with self._tcp_server:
            await self._tcp_server.serve_forever()

    def _schedule_session(
            self,
            reader: asyncio.StreamReader,
            writer: asyncio.StreamWriter,
            sessions_factory: Callable[[asyncio.StreamReader, asyncio.StreamWriter], _T],
            ):
        session = sessions_factory(reader, writer)
        session.add_done_callback(self._session_finalizer)
        self._sessions.add(session)

    def _session_finalizer(self, finished_session: _ConcurrentSession):
        self._sessions.discard(finished_session)
        exception = finished_session.get_exception()
        if exception is not None:
            logging.exception("%s is done with exception", exc_info=exception)

    def _close_sessions(self):
        for session in self._sessions:
            session.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._close_sessions()
        await self._wait_closed()

    async def _wait_closed(self):
        _logger.info("Waiting for sessions to complete: %s ...", self._sessions)
        wait_sessions_closed = (session.wait_closed() for session in self._sessions)
        wait_timeout = 10
        await asyncio.wait_for(asyncio.gather(*wait_sessions_closed), timeout=wait_timeout)
        _logger.info("Server is closed")

    def __repr__(self):
        listen_ip, listen_port = self._server_socket.getsockname()
        return f'<Server on {listen_ip}:{listen_port}>'


class MarketARMSession(_ConcurrentSession):

    def __init__(
            self,
            reader: asyncio.StreamReader,
            writer: asyncio.StreamWriter,
            markets: Sequence[Market],
            ):
        super().__init__(reader, writer)
        self._markets = markets
        self._pending_contracts: dict[str, SignedContract] = {}

    async def _serve(self):
        _logger.info("%s: Start serving session", self)
        try:
            self._greet_client()
            await self._handle_requests_loop()
        except ConnectionError as e:
            _logger.warning("%s: Connection has lost due to %s", self, e)
        except Exception as err:
            err_msg = f"{err.__class__.__name__}: {err}"
            _logger.exception("Server exception has occurred: %s", err_msg)
            self._send_err(err_msg)
        finally:
            self._close_pending_contracts()
        _logger.info("%s: Session closed", self)

    def _greet_client(self):
        greet_msg = f"You're welcome {self._peername}"
        status_msg = Greet(greet_msg)
        self._send_status(status_msg)

    async def _handle_requests_loop(self):
        async for request in self._requests_reader():
            self._send_status(Ack())
            await self._handle_request(request)

    async def _requests_reader(self) -> AsyncGenerator[RequestMsg, None]:
        while True:
            try:
                line = await self._reader.readuntil(_EOL)
            except asyncio.IncompleteReadError:
                _logger.info("%s: Connection closed", self)
                return
            line = line.strip()
            _logger.debug("%s: Request received: %s", self, line)
            yield RequestMsg.from_bytes(line)

    async def _handle_request(self, request: RequestMsg):
        _type = request.type
        if _type == RequestType.UNLOCK_MACHINE:
            status_message = await self._unlock_machine_handler(request.data)
        elif _type == RequestType.GET_SNAPSHOT:
            status_message = await self._get_snapshot_handler(request.data)
        elif _type == RequestType.COMMIT_SNAPSHOT:
            status_message = await self._commit_snapshot_handler(request.data)
        else:
            errmsg = f"Can't find handler for request {request!r}"
            self._send_err(errmsg)
            raise RuntimeError(errmsg)
        if status_message is None:
            raise RuntimeError("Handler return values must not be None")
        self._send_status(status_message)

    def _send_status(self, status_msg: StatusMsg):
        _logger.debug("%s: Send status: %s", self, status_msg)
        self._writer.write(status_msg.as_bytes() + _EOL)

    def _send_err(self, errmsg: str):
        return self._send_status(Error(message=errmsg))

    async def _get_snapshot_handler(self, request: Mapping[str, Any]):
        request_timeout = request.get('timeout', 1800)
        contract_description = request['description']
        market = self._markets[request['priority']]
        contractor_info: LockedMachineClientInfo
        try:
            contract, contractor_info = await asyncio.wait_for(
                market.find_contractor(contract_description), timeout=request_timeout)
        except ContractRejected as err:
            return Nok(str(err))
        contractor_name = contractor_info['machine_name']
        self._pending_contracts[contractor_name] = contract
        return Ok({'clients': [contractor_info]})

    async def _unlock_machine_handler(self, request: ReleaseMachineRequest):
        contractor_name = request['machine_name']
        pending_contract = self._pending_contracts.pop(contractor_name, None)
        if pending_contract is not None:
            pending_contract.close()
        return Ok({})

    async def _commit_snapshot_handler(self, request: CommitSnapshotRequest):
        machine_name = request['machine_name']
        contract = self._pending_contracts.pop(machine_name, None)
        if contract is None:
            raise RuntimeError(f"Can't find locked machine {machine_name}")
        with closing(contract):
            try:
                await contract.execute_sync({'snapshot': 'commit'})
            except CommandFailed as err:
                _logger.exception("%s: %s sent committing snapshot error:", self, machine_name)
                return Error(f"Can't commit snapshot on {machine_name}: {str(err)}")
            except ContractorQuit as err:
                _logger.exception("%s: %s quit while committing snapshot", self, machine_name)
                return Error(f"Can't commit snapshot on {machine_name}: {str(err)}")
            return Ok({})

    def close(self):
        if not self._writer.is_closing():
            _logger.info("Close session %s", self._peername)
            self._writer.close()

    async def wait_closed(self):
        await asyncio.gather(self._task, self._wait_writer_closed())

    def _close_pending_contracts(self):
        for pending_contract in self._pending_contracts.values():
            pending_contract.close()
        self._pending_contracts.clear()

    async def _wait_writer_closed(self):
        try:
            await self._writer.wait_closed()
        except (ConnectionError, asyncio.IncompleteReadError):
            pass
        _logger.info("%s: is closed", self)

    def __repr__(self):
        return f"<Session {self._peername}>"
