# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import asyncio
import os
import socket
import time
from abc import ABCMeta
from abc import abstractmethod
from collections.abc import Mapping
from contextlib import AbstractAsyncContextManager
from contextlib import AbstractContextManager
from contextlib import asynccontextmanager
from contextlib import contextmanager
from pathlib import Path
from typing import TypeVar

_T = TypeVar('_T', bound=Mapping[str, str])


class StatusEndpoint(metaclass=ABCMeta):

    @abstractmethod
    def serving(self) -> AbstractContextManager:
        yield

    @abstractmethod
    async def aclose(self):
        pass


class UnixSocketStatusEndpoint(StatusEndpoint):

    def __init__(self, socket_path: Path):
        self._socket_path = socket_path
        with _file_mask(0o777):  # Status endpoint is intended to be used by any user.
            self._unix_socket = _open_asyncio_stream_socket(str(socket_path))
        self._loop = asyncio.get_running_loop()
        self._task = self._loop.create_task(self._serve_loop(), name='serve_loop')
        self._status = _Status()

    @contextmanager
    def serving(self):
        self._status.set_running()
        try:
            yield
        except Exception:
            self._status.inc_failures()
            raise
        else:
            self._status.inc_successes()
        finally:
            self._status.set_idle()

    async def _serve_loop(self):
        while True:
            try:
                await self._handle_next_stream()
            except OSError:
                pass

    async def _handle_next_stream(self):
        async with self._opened_writer() as writer:  # type: asyncio.StreamWriter
            await self._status.send_to(writer)

    @asynccontextmanager
    async def _opened_writer(self) -> AbstractAsyncContextManager[asyncio.StreamWriter]:
        client_socket, _address = await self._loop.sock_accept(self._unix_socket)
        _reader, writer = await asyncio.open_unix_connection(sock=client_socket)
        try:
            yield writer
        finally:
            writer.close()
            await writer.wait_closed()

    async def aclose(self):
        self._unix_socket.close()
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass

    def __repr__(self):
        return f'{self.__class__.__name__}: {self._socket_path}'


@contextmanager
def _file_mask(mode: int):
    # Default umask value is defined in /etc/login.defs
    # See: https://man7.org/linux/man-pages/man2/umask.2.html
    old_mode = os.umask(mode ^ 0o777)
    try:
        yield
    finally:
        os.umask(old_mode)


def _open_asyncio_stream_socket(raw_path: str) -> socket.socket:
    listen_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listen_socket.bind(raw_path)
    listen_socket.listen()
    listen_socket.setblocking(False)
    return listen_socket


class _StatusEnum:

    IDLE = 'IDLE'
    RUNNING = 'RUNNING'


class _Status:

    def __init__(self):
        self._start_at = time.monotonic()
        self._successes = 0
        self._failures = 0
        self._status = _StatusEnum.IDLE

    def inc_successes(self):
        self._successes += 1

    def inc_failures(self):
        self._failures += 1

    def set_idle(self):
        self._status = _StatusEnum.IDLE

    def set_running(self):
        self._status = _StatusEnum.RUNNING

    async def send_to(self, writer: asyncio.StreamWriter):
        writer.write(self._status_text())
        await writer.drain()

    def _status_text(self) -> bytes:
        result = bytearray()
        result.extend(f"Status: {self._status}\n".encode())
        result.extend(f"Successes: {self._successes}\n".encode())
        result.extend(f"Failures: {self._failures}\n".encode())
        uptime = time.monotonic() - self._start_at
        result.extend(f"Uptime: {uptime:.03f}\n".encode())
        return result
