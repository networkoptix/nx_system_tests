# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import asyncio
import errno
import fcntl
import json
import logging
import os
import socket
import time
from abc import ABCMeta
from abc import abstractmethod
from collections.abc import AsyncIterable
from collections.abc import AsyncIterator
from collections.abc import Mapping
from contextlib import AbstractAsyncContextManager
from contextlib import asynccontextmanager
from contextlib import closing
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from typing import Union

# DEBUG asyncio logs contain many low-level IO-bound errors which do not affect execution process
# Any really important messages are written to WARNING level
# See: https://docs.python.org/3/library/asyncio-dev.html#logging
logging.getLogger("asyncio").setLevel(logging.INFO)


class Market(metaclass=ABCMeta):

    @abstractmethod
    async def find_contractor(
            self,
            contract_description: Mapping[str, Any],
            ) -> tuple['SignedContract', Mapping[str, Any]]:
        pass

    @abstractmethod
    async def iter_pending_contracts(self) -> AsyncIterator[tuple['Contract', Mapping[str, Any]]]:
        yield


class SignedContract(metaclass=ABCMeta):

    @abstractmethod
    async def execute_sync(self, command_description: Mapping[str, Any]) -> Mapping[str, Any]:
        pass

    @abstractmethod
    def close(self):
        pass


class Contract(metaclass=ABCMeta):

    @abstractmethod
    async def accepted(
            self,
            contractor_info: Mapping[str, Any],
            ) -> AbstractAsyncContextManager['AcceptedContract']:
        yield

    @abstractmethod
    async def reject(self, message: str):
        pass

    @abstractmethod
    def ignore(self):
        pass


class AcceptedContract(metaclass=ABCMeta):

    @abstractmethod
    async def handle(self) -> AsyncIterator[tuple['PendingCommand', Mapping[str, Any]]]:
        yield


class PendingCommand(metaclass=ABCMeta):

    @abstractmethod
    async def report_success(self, result: Mapping[str, Any]):
        pass

    @abstractmethod
    async def report_failure(self, result: Mapping[str, Any]):
        pass


class SocketsOrderedStorage(metaclass=ABCMeta):

    @abstractmethod
    def open_new(self, group: str) -> socket.socket:
        pass

    @abstractmethod
    async def iter_active_by_age(self, group: str) -> AsyncIterator[socket.socket]:
        yield


class SingleDirectoryStorage(SocketsOrderedStorage):

    _temporary_suffix = '.tmp'

    def __init__(self, directory: Path):
        if not directory.exists():
            raise RuntimeError(f"{directory} does not exist")
        self._directory = directory

    def open_new(self, group: str) -> socket.socket:
        timestamped_unique_socket_name = f'{group}_{time.time():.07f}_{os.getpid()}.sock'
        socket_name = self._directory / timestamped_unique_socket_name
        with self._exclusive_lock():
            self._clean_orphaned_temporary_sockets()
            return self._open_unix_socket_atomically(socket_name)

    async def iter_active_by_age(self, group: str) -> AsyncIterator[socket.socket]:
        socket_files_by_age = sorted(self._directory.glob(f'{group}_*.sock'))
        for socket_path in socket_files_by_age:
            try:
                opened_unix_socket = await _connected_unix_socket(
                    str(socket_path), connection_timeout=1)
            except FileNotFoundError:
                _logger.debug("%r: %s is not found, probably it is removed", self, socket_path)
                continue
            except BlockingIOError:
                _logger.debug("%r: %s is already being processed", self, socket_path)
                continue
            except TimeoutError:
                _logger.warning("%r: %s timed out. Pass it by", self, socket_path)
                continue
            except PermissionError:
                _logger.error(
                    "%r: Don't have sufficient permissions to open %s", self, socket_path)
                continue
            except ConnectionRefusedError:
                _logger.debug("%r: Remove defunct artifact %s", self, socket_path)
                socket_path.unlink(missing_ok=True)
                continue
            except Exception:
                _logger.exception("%r: Opening of %s raised an exception", self, socket_path)
                continue
            yield opened_unix_socket

    def _open_unix_socket_atomically(self, socket_path: Path) -> socket.socket:
        # A ConnectionRefusedError is raised at attempt to connect to a unix socket between
        # socket.bind() and socket.listen()
        temporary_socket = socket_path.with_name(socket_path.name + self._temporary_suffix)
        with _file_mask(0o777):  # Storage is intended to be used and maintained by any user.
            opened_socket = _open_point_to_point_unix_socket(str(temporary_socket))
        temporary_socket.replace(socket_path)
        return opened_socket

    @contextmanager
    def _exclusive_lock(self):
        # Pathlib does not allow opening a directory via Path.open()
        fd = os.open(self._directory, flags=os.O_RDONLY)
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            yield
        finally:
            os.close(fd)

    def _clean_orphaned_temporary_sockets(self):
        for file in self._directory.glob(f'*{self._temporary_suffix}'):
            file.unlink()

    def __repr__(self):
        return f'<SocketsStorage: {self._directory}>'


@contextmanager
def _file_mask(mode: int):
    # Default umask value is defined in /etc/login.defs
    # See: https://man7.org/linux/man-pages/man2/umask.2.html
    old_mode = os.umask(mode ^ 0o777)
    try:
        yield
    finally:
        os.umask(old_mode)


def _open_point_to_point_unix_socket(raw_path: str) -> socket.socket:
    listen_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listen_socket.setblocking(False)
    listen_socket.bind(raw_path)
    listen_socket.listen(0)
    return listen_socket


async def _connected_unix_socket(raw_path: str, connection_timeout: float) -> socket.socket:
    client_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client_socket.setblocking(False)
    connect_coroutine = asyncio.get_running_loop().sock_connect(client_socket, raw_path)
    try:
        await asyncio.wait_for(connect_coroutine, timeout=connection_timeout)
    except Exception:
        client_socket.close()
        raise
    return client_socket


class UnixSocketMarket(Market):

    def __init__(self, sockets_storage: SocketsOrderedStorage, priority: int):
        self._sockets_storage = sockets_storage
        self._priority_prefix = f'{priority:02d}'

    async def find_contractor(
            self,
            contract_description: Mapping[str, Any],
            ) -> tuple['_UnixSocketSignedContract', Mapping[str, Any]]:
        new_socket = self._sockets_storage.open_new(self._priority_prefix)
        with closing(_UnixSocketTender(new_socket, contract_description)) as tender:  # type: _UnixSocketTender
            return await tender.wait_signed_contract()

    async def iter_pending_contracts(
            self) -> AsyncIterator[tuple['_UnixContract', Mapping[str, Any]]]:
        async for stream in self._iter_opened_streams():
            try:
                description_message = await asyncio.wait_for(
                    _ContractDescriptionMessage.read(stream), timeout=1)
            except (_StreamClosed, TimeoutError):
                continue
            yield _UnixContract(stream), description_message.get_description()

    async def _iter_opened_streams(self) -> AsyncIterable['_JsonStream']:
        async for client_socket in self._sockets_storage.iter_active_by_age(self._priority_prefix):
            try:
                stream = await _JsonStream.wrap(client_socket)
            except OSError:
                continue
            yield stream

    def __repr__(self):
        return f'<{self.__class__.__name__} {self._sockets_storage}:[{self._priority_prefix}]>'


class _UnixContract(Contract):

    def __init__(self, stream: '_JsonStream'):
        self._stream = stream

    @asynccontextmanager
    async def accepted(
            self,
            contractor_info: Mapping[str, Any],
            ) -> AbstractAsyncContextManager['AcceptedContract']:
        with closing(self._stream):
            try:
                await _ContractStatusMessage.executing(contractor_info).send(self._stream)
            except _StreamClosed:
                raise RuntimeError("Contract is broken without proper termination")
            yield _UnixSocketAcceptedContract(self._stream)

    async def reject(self, message: str):
        with closing(self._stream):
            try:
                await _ContractStatusMessage.reject(message).send(self._stream)
            except _StreamClosed:
                pass

    def ignore(self):
        self._stream.close()


class _UnixSocketAcceptedContract(AcceptedContract):

    def __init__(self, stream: '_JsonStream'):
        self._stream = stream

    async def handle(self) -> AsyncIterator[tuple['PendingCommand', Mapping[str, Any]]]:
        while True:
            try:
                command = await _CommandMessage.read(self._stream)
            except _StreamClosed:
                return
            yield _UnixSocketPendingCommand(self._stream), command.get_command()


class _UnixSocketPendingCommand(PendingCommand):

    def __init__(self, stream: '_JsonStream'):
        self._stream = stream

    async def report_success(self, result: Mapping[str, Any]):
        try:
            await _CommandResult.success(result).send(self._stream)
        except _StreamClosed:
            raise RuntimeError("Contract is broken without proper termination")

    async def report_failure(self, result: Mapping[str, Any]):
        try:
            await _CommandResult.failure(result).send(self._stream)
        except _StreamClosed:
            raise RuntimeError("Contract is broken without proper termination")


class _UnixSocketTender:

    def __init__(self, listen_socket: socket.socket, contract_description: Mapping[str, Any]):
        self._listen_socket = listen_socket
        self._contract_description = _ContractDescriptionMessage(contract_description)
        self._repr = self._listen_socket.getsockname()

    async def wait_signed_contract(self) -> tuple['_UnixSocketSignedContract', Mapping[str, Any]]:
        async for client_stream in self._iter_client_streams():
            try:
                contract_status = await self._offer_contract(client_stream)
            except (_StreamClosed, TimeoutError):
                _logger.debug("%r: Offer is ignored by %s", self, client_stream)
                client_stream.close()
                continue
            try:
                contractor_info = contract_status.get_contractor_info()
            except ContractRejected:
                client_stream.close()
                raise
            return _UnixSocketSignedContract(client_stream), contractor_info

    def close(self):
        self._listen_socket.close()

    async def _wait_new_stream(self) -> '_JsonStream':
        client_sock, _address = await asyncio.get_running_loop().sock_accept(self._listen_socket)
        try:
            return await _JsonStream.wrap(client_sock)
        except OSError:
            client_sock.close()
            raise

    async def _iter_client_streams(self) -> AsyncIterator['_JsonStream']:
        while True:
            try:
                stream = await self._wait_new_stream()
            except OSError as os_error:
                _logger.warning("%r: Error at stream open", self, exc_info=os_error)
                continue
            yield stream

    async def _offer_contract(self, client_stream: '_JsonStream') -> '_ContractStatusMessage':
        await self._contract_description.send(client_stream)
        return await asyncio.wait_for(
            _ContractStatusMessage.read(client_stream), timeout=10)

    def __repr__(self):
        return f"<UnixSocketTender: {self._repr}>"


class _UnixSocketSignedContract(SignedContract):

    def __init__(self, stream: '_JsonStream'):
        self._stream = stream

    async def execute_sync(self, command_description: Mapping[str, Any]) -> Mapping[str, Any]:
        try:
            await _CommandMessage(command_description).send(self._stream)
            result = await _CommandResult.read(self._stream)
        except _StreamClosed:
            raise ContractorQuit()
        return result.get_description()

    def close(self):
        self._stream.close()


class _JsonStream:

    _EOL = b'\n'

    @classmethod
    async def wrap(cls, unix_socket: socket.socket):
        reader, writer = await asyncio.open_unix_connection(sock=unix_socket)
        return cls(reader, writer)

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self._reader = reader
        self._writer = writer
        if sock_name := writer.get_extra_info('sockname'):
            self._repr = f'<JSONServerStream: {sock_name}>'
        elif sock_name := writer.get_extra_info('peername'):
            self._repr = f'<JSONClientStream: {sock_name}>'
        else:
            socket_object = writer.get_extra_info('socket')
            self._repr = f'<DefunctStream: {socket_object}>'

    async def send(self, json_object: Mapping[str, Any]):
        encoded_json = json.dumps(json_object).encode('utf-8')
        _logger.debug("%r: Sending %s ...", self, encoded_json)
        try:
            self._writer.write(encoded_json + self._EOL)
            await self._writer.drain()
        except ConnectionError:
            raise _StreamClosed()
        _logger.debug("%r: Sent", self)

    async def read_object(self) -> Mapping[str, Any]:
        _logger.debug("%r: Waiting for data ...", self)
        try:
            json_bytes = await self._reader.readuntil(self._EOL)
        except ConnectionResetError:
            _logger.debug("%r: Peer has gone after receiving data", self)
            raise _StreamClosed()
        except asyncio.IncompleteReadError:
            _logger.debug("%r: Peer has closed the stream gracefully", self)
            raise _StreamClosed()
        except OSError as err:
            if err.errno == errno.EINVAL:
                _logger.debug("%r: Peer has gone before attempting to read sent data", self)
                raise _StreamClosed()
            raise
        _logger.debug("%r: Received data %s", self, json_bytes)
        return json.loads(json_bytes)

    def close(self):
        self._writer.close()

    def __repr__(self):
        return self._repr


class _ContractDescriptionMessage:

    _type = 'contract_description'

    @classmethod
    async def read(cls, stream: '_JsonStream'):
        message = await stream.read_object()
        if message['type'] != cls._type:
            raise RuntimeError(
                f"Unexpected message type instead {cls._type!r}: {message['type']!r}")
        return cls(message['description'])

    def __init__(self, description: Mapping[str, Any]):
        self._description = description

    def get_description(self) -> Mapping[str, Any]:
        return self._description

    async def send(self, stream: '_JsonStream'):
        await stream.send({'type': self._type, 'description': self._description})

    def __repr__(self):
        return f'<Contract: {self._description}>'


class _ContractStatusMessage:

    _type = 'job_status'
    _status_executing = 'executing'
    _status_rejected = 'rejected'

    @classmethod
    def executing(cls, performer_info: Mapping[str, Any]):
        return cls(cls._status_executing, performer_info)

    @classmethod
    def reject(cls, message: str):
        return cls(cls._status_rejected, message)

    @classmethod
    async def read(cls, stream: '_JsonStream'):
        message = await stream.read_object()
        if message['type'] != cls._type:
            raise RuntimeError(f"Unexpected message type instead {cls._type!r}: {message['type']!r}")
        return cls(message['status'], message['info'])

    def __init__(self, status: str, info: Union[str, Mapping[str, Any]]):
        self._status = status
        self._info = info

    def get_contractor_info(self) -> Mapping[str, Any]:
        if self._status == self._status_rejected:
            raise ContractRejected(self._info)
        return self._info

    async def send(self, stream: '_JsonStream'):
        await stream.send({'type': self._type, 'status': self._status, 'info': self._info})


class _CommandMessage:

    _type = 'command'

    @classmethod
    async def read(cls, stream: '_JsonStream'):
        message = await stream.read_object()
        if message['type'] != cls._type:
            raise RuntimeError(f"Unexpected message type instead {cls._type!r}: {message['type']!r}")
        return cls(message['command'])

    def __init__(self, command: Mapping[str, Any]):
        self._command = command

    def get_command(self) -> Mapping[str, Any]:
        return self._command

    async def send(self, stream: '_JsonStream'):
        await stream.send({'type': self._type, 'command': self._command})

    def __repr__(self):
        return f'<Command {self._command}>'


class _CommandResult:

    _type = 'command_result'
    _success = 'success'
    _failure = 'failure'

    @classmethod
    def success(cls, description: Mapping[str, Any]):
        return cls(cls._success, description)

    @classmethod
    def failure(cls, description: Mapping[str, Any]):
        return cls(cls._failure, description)

    @classmethod
    async def read(cls, stream: '_JsonStream'):
        message = await stream.read_object()
        if message['type'] != cls._type:
            raise RuntimeError(f"Unexpected message type instead {cls._type!r}: {message['type']!r}")
        return cls(message['status'], message['result_description'])

    def __init__(self, status: str, result_description: Mapping[str, Any]):
        self._status = status
        self._result_description = result_description

    def get_description(self) -> Mapping[str, Any]:
        if self._status == self._failure:
            raise CommandFailed(self._result_description)
        return self._result_description

    async def send(self, stream: '_JsonStream'):
        await stream.send({
            'type': self._type,
            'status': self._status,
            'result_description': self._result_description,
            })

    def __repr__(self):
        return f'<CommandResult: [{self._status}] {self._result_description}>'


class _StreamClosed(Exception):
    pass


class ContractorQuit(Exception):
    pass


class ContractRejected(Exception):
    pass


class CommandFailed(Exception):

    def __init__(self, description: Mapping[str, Any]):
        super().__init__()
        self.result = description

    def __str__(self):
        return f"{self.result!r}"


_logger = logging.getLogger(__name__)
