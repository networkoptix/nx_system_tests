# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import asyncio
import ipaddress
import logging
import socket
from contextlib import asynccontextmanager
from multiprocessing import Process
from typing import AsyncContextManager
from typing import Set

from arms.usb_emulation.api.async_queue import TaskQueue
from arms.usb_emulation.api.mass_storage import run_mass_storage
from arms.usb_emulation.api.protocol import Request
from arms.usb_emulation.api.protocol import RequestType
from arms.usb_emulation.api.protocol import Response

_logger = logging.getLogger(__name__)


class ApiServer:
    def __init__(
            self,
            adapter_addresses_by_name: dict[str, ipaddress.IPv4Address],
            api_host: str,
            api_port: int,
            ):
        self._tasks: Set[asyncio.Task] = set()
        self._adapter_addresses_by_name = adapter_addresses_by_name
        self._host = api_host
        self._port = api_port
        self._queues = TaskQueue(adapter_addresses_by_name.keys())
        self._processes: dict[str, Process] = {}
        self._socket = server_socket(api_host, api_port)

    async def __aenter__(self):
        self._start_processes()
        _logger.info("All Processes started")
        return self

    def add_disk(self, machine_name: str, disk_size: int):
        self._queues.get_queue(machine_name).put_nowait(disk_size)

    def _start_processes(self):
        for name, address in self._adapter_addresses_by_name.items():
            self._start_single_process(address, name)

    def _start_single_process(self, address, name):
        self._processes[name] = Process(
            target=run_mass_storage,
            args=(address, self._queues.get_queue(name)))
        self._processes[name].start()

    def _close_process(self, name: str):
        if (process := self._processes[name]).is_alive():
            process.terminate()
        else:
            process.join()

    def _close_all_processes(self):
        _logger.info("Closing all processes")
        for name in self._adapter_addresses_by_name:
            self._close_process(name)

    async def _handle_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            content = await reader.readline()
            request = Request.unpack(content.decode("utf-8"))
            if request.type == RequestType.ADD:
                self.add_disk(request.name, request.size)
                writer.write(str(Response.ok()).encode('utf-8') + b'\n')
            elif request.type == RequestType.DELETE:
                self._close_process(request.name)
                self._start_single_process(
                    self._adapter_addresses_by_name[request.name],
                    request.name)
                writer.write(str(Response.ok()).encode('utf-8') + b'\n')
            else:
                response = Response.error(f"Unknown type {request.type}")
                writer.write(str(response).encode('utf-8') + b'\n')
        except Exception as e:
            writer.write(str(Response.error(str(e))).encode() + b'\n')
            raise
        finally:
            writer.close()
            await writer.wait_closed()

    def schedule_session(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        [remote_ip, remote_port] = writer.get_extra_info('peername')  # type: str, int
        task_name = f"Session {remote_ip}:{remote_port}"
        task = asyncio.Task(self._handle_connection(reader, writer), name=task_name)
        task.add_done_callback(self._task_finalizer)
        self._tasks.add(task)

    def _task_finalizer(self, task: asyncio.Task):
        self._tasks.discard(task)
        # noinspection PyBroadException
        try:
            task.result()
        except Exception:
            _logger.exception("Server task exception:")

    @asynccontextmanager
    async def serve(self) -> AsyncContextManager[asyncio.AbstractServer]:
        async_server = await asyncio.start_server(
            client_connected_cb=self.schedule_session,
            sock=self._socket,
            )
        async with async_server:
            yield async_server

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        _logger.info("Waiting for tasks to complete: %s", list(self._tasks))
        tasks = await asyncio.gather(*self._tasks, return_exceptions=True)
        for task_result in tasks:
            if isinstance(task_result, BaseException):
                _logger.exception("Wait_closed_exception", exc_info=task_result)
                raise task_result
        _logger.info("Server is closed")
        self._close_all_processes()


def server_socket(listen_host: str, listen_port: int) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)

    sock.bind((listen_host, listen_port))
    sock.setblocking(False)
    _logger.info("TCP Server is opened on %s:%s", listen_host, listen_port)
    return sock
