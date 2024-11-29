# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import asyncio
import logging
import socket
from contextlib import asynccontextmanager
from contextlib import suppress
from typing import AsyncContextManager
from typing import Callable
from typing import Optional
from typing import Set

from usb_emulation.usb.usb_descriptors import StandardDeviceRequest
from usb_emulation.usb.usb_device import UsbDevice
from usb_emulation.usb.usb_registry import BadBusIdError
from usb_emulation.usb.usb_registry import DeviceNotFoundError
from usb_emulation.usb.usb_registry import UsbDeviceRegistry
from usb_emulation.usb_ip.usbip_protocol import EmptyBody
from usb_emulation.usb_ip.usbip_protocol import EmptyHeader
from usb_emulation.usb_ip.usbip_protocol import OPREQImport
from usb_emulation.usb_ip.usbip_protocol import USBIPCMDSubmit
from usb_emulation.usb_ip.usbip_protocol import USBIPCMDSubmitHeader
from usb_emulation.usb_ip.usbip_protocol import USBIPHeader
from usb_emulation.usb_ip.usbip_protocol import USBIPRETSubmit
from usb_emulation.usb_ip.usbip_protocol import USBIP_BUS_ID_SIZE
from usb_emulation.usb_ip.usbip_protocol import USBIP_COMMAND_ATTACH_CODE
from usb_emulation.usb_ip.usbip_protocol import USBIP_COMMAND_DEVLIST_CODE
from usb_emulation.usb_ip.usbip_protocol import USB_IP_DEVICE_ERROR
from usb_emulation.usb_ip.usbip_protocol import USB_IP_DEVICE_USED
from usb_emulation.usb_ip.usbip_protocol import USB_IP_GENERIC_ERROR
from usb_emulation.usb_ip.usbip_protocol import usb_ip_rep_import_header
from usb_emulation.usb_ip.usbip_session import ConnectionClosed
from usb_emulation.usb_ip.usbip_session import usb_device_list_to_op_rep_list

_logger = logging.getLogger(__name__)


class AsyncUsbIpConnection:
    def __init__(
            self,
            reader: asyncio.StreamReader,
            writer: asyncio.StreamWriter,
            device: UsbDevice,
            registry: UsbDeviceRegistry,
            ):
        self._reader = reader
        self._writer = writer
        self._device = device
        self._registry = registry

    def send_usb_response(
            self,
            seqnum: int,
            usb_res: bytes,
            endpoint: int = 0,
            status: int = 0,
            ):
        self._writer.write(
            bytes(
                USBIPRETSubmit.create_response(
                    seqnum=seqnum,
                    status=status,
                    endpoint=endpoint,
                    data=usb_res),
                ),
            )
        _logger.debug("Send response for seq number: %d", seqnum)

    def send_usb_ack(
            self,
            usb_req: USBIPCMDSubmit,
            ack_value: int,
            ):
        self._writer.write(
            bytes(USBIPRETSubmit.create_ack(seqnum=usb_req.seqnum, ack_value=ack_value)),
            )
        _logger.debug("Ack response for seq number: %d, ack value: %d", usb_req.seqnum, ack_value)

    def handle_usb_request(
            self,
            usb_request: USBIPCMDSubmit,
            control_request: StandardDeviceRequest,
            ):
        if usb_request.ep == 0:
            result = self._device.handle_usb_control(control_request)
        else:
            _logger.info("Handle data request")
            result = self._device.handle_data(
                data=usb_request.data,
                endpoint=usb_request.ep,
                transfer_length=usb_request.header.transfer_buffer_length)
        if result is not None:
            if not result.ack:
                self.send_usb_response(
                    usb_request.seqnum,
                    result.data,
                    status=result.status,
                    )
            else:
                self.send_usb_ack(usb_request, result.ack_value)
        else:
            _logger.warning("No response for request %s", str(usb_request))

    async def handle_usbip_submit(self):
        try:
            header = USBIPCMDSubmitHeader.unpack(await self._reader.readexactly(USBIPCMDSubmitHeader.size))
            data = b''
            if header.direction == 0 and header.transfer_buffer_length > 0:
                data = await self._reader.readexactly(header.transfer_buffer_length)
            usb_request = USBIPCMDSubmit(header=header, data=data)
        except EmptyBody as e:
            self.send_usb_response(e.seqnum, b'', status=USB_IP_GENERIC_ERROR)  # todo define constants
            raise ConnectionClosed()
        except EmptyHeader:
            raise ConnectionClosed()
        control_request = StandardDeviceRequest.unpack(usb_request.setup)
        try:
            self.handle_usb_request(usb_request, control_request)
        except Exception as err:
            err_msg = f"{err.__class__.__name__}: {err}"
            _logger.exception("An  exception has occurred in USB IP connection: %s", err_msg)
            self.send_usb_response(usb_request.seqnum, b'', status=USB_IP_DEVICE_ERROR)
            raise ConnectionClosed()

    def release(self):
        self._device.release()
        self._registry.release_device(self._device)


class AsyncUsbIpSession:

    def __init__(
            self,
            reader: asyncio.StreamReader,
            writer: asyncio.StreamWriter,
            registry: UsbDeviceRegistry,
            ):
        self._name = self._get_connection_name(writer)
        self._reader = reader
        self._writer = writer
        self._registry = registry
        self._established_connection: Optional[AsyncUsbIpConnection] = None

    def __str__(self):
        return f"Session {self._name}"

    def _handle_device_list(self):
        _logger.info("Handle device list")
        self._writer.write(bytes(usb_device_list_to_op_rep_list(self._registry.list_devices())))

    def _handle_attach(self, import_request: OPREQImport):
        _logger.info("Attaching device")
        try:
            usb_device = self._registry.fetch_by_bus_id(import_request.bus_id)
            _logger.info("Obtained %s", usb_device)
        except DeviceNotFoundError:
            self._writer.write(
                bytes(usb_ip_rep_import_header(status=USB_IP_DEVICE_USED)))
            raise ConnectionClosed()
        except BadBusIdError:
            self._writer.write(
                bytes(usb_ip_rep_import_header(status=USB_IP_GENERIC_ERROR)))
            raise ConnectionClosed()
        self._writer.write(bytes(usb_device.get_usbip_op_rep_import()))
        self._established_connection = AsyncUsbIpConnection(
            reader=self._reader,
            writer=self._writer,
            device=usb_device,
            registry=self._registry,
            )

    async def _get_usb_ip_header(self):
        data = await self._reader.read(USBIPHeader.size)
        if not data:
            return None
        return USBIPHeader.unpack(data)

    async def _establish_connection(self):
        usbip_header = await self._get_usb_ip_header()
        if usbip_header is None:
            raise ConnectionClosed("No header received")
        await self._dispatch_usb_ip_header(usbip_header)

    async def serve(self):
        _logger.info("%s: Start serving session", self)
        try:
            await self._establish_connection()
            if self._established_connection is None:
                # if connection was not established
                # the request was devlist
                return
            while True:
                await self._established_connection.handle_usbip_submit()
        except (ConnectionClosed, ConnectionError, asyncio.IncompleteReadError):
            _logger.info("Closing connection.")

    async def _dispatch_usb_ip_header(self, header: USBIPHeader):
        if header.command == USBIP_COMMAND_DEVLIST_CODE:
            self._handle_device_list()
        elif header.command == USBIP_COMMAND_ATTACH_CODE:
            import_request = OPREQImport(header, await self._reader.readexactly(USBIP_BUS_ID_SIZE))
            self._handle_attach(import_request)

    def _release_resources(self):
        if self._established_connection is not None:
            self._established_connection.release()

    def close(self):
        if not self._writer.is_closing():
            _logger.info("Close session %s", self._name)
            self._writer.close()

    async def _wait_closed(self):
        self._release_resources()
        await self._wait_writer_closed()

    async def _wait_writer_closed(self):
        with suppress(ConnectionError, asyncio.IncompleteReadError):
            await self._writer.wait_closed()
        _logger.info("%s: is closed", self)

    async def __aenter__(self):
        _logger.info("%s is opened", self)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.close()
        await self._wait_closed()

    @staticmethod
    def _get_connection_name(writer: asyncio.StreamWriter) -> str:
        remote_ip, remote_port = writer.get_extra_info('peername')  # type: str, int
        return f"{remote_ip}:{remote_port}"


class UsbIpStreamServer:
    def __init__(
            self,
            listen_host: str = '0.0.0.0',
            listen_port: int = 3240,
            ):
        self._listen_host = listen_host
        self._listen_port = listen_port
        self._bind_socket()

    def _bind_socket(self):
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self._server_socket.bind((self._listen_host, self._listen_port))
        _logger.info("USB IP Server is opened on %s:%s", self._listen_host, self._listen_port)

    @asynccontextmanager
    async def serve(
            self,
            session_callback: Callable[[asyncio.StreamReader, asyncio.StreamWriter], None],
            ) -> AsyncContextManager[asyncio.AbstractServer]:
        async_server = await asyncio.start_server(
            client_connected_cb=session_callback,
            sock=self._server_socket,
            )
        async with async_server:
            yield async_server


class UsbIpSessionsManager:

    def __init__(self, usb_device_registry: UsbDeviceRegistry):
        self._tasks: Set[asyncio.Task] = set()
        self._usb_device_registry = usb_device_registry
        self._sessions: Set[AsyncUsbIpSession] = set()

    def schedule_session(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        remote_ip, remote_port = writer.get_extra_info('peername')  # type: str, int
        task_name = f"Session {remote_ip}:{remote_port}"
        task = asyncio.Task(self._client_session(reader, writer), name=task_name)
        task.add_done_callback(self._task_finalizer)
        self._tasks.add(task)

    def _task_finalizer(self, task: asyncio.Task):
        self._tasks.discard(task)
        # noinspection PyBroadException
        try:
            task.result()
        except Exception:
            _logger.exception("Server task exception:")

    async def _wait_closed(self):
        _logger.info("Waiting for tasks to complete: %s", list(self._tasks))
        tasks = await asyncio.gather(*self._tasks, return_exceptions=True)
        for task_result in tasks:
            if isinstance(task_result, BaseException):
                _logger.exception("Wait_closed_exception", exc_info=task_result)
                raise task_result
        _logger.info("Server is closed")

    def _close_sessions(self):
        for session in self._sessions:
            session.close()

    async def _client_session(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        async with AsyncUsbIpSession(reader, writer, self._usb_device_registry) as session:
            self._sessions.add(session)
            try:
                await session.serve()
            finally:
                self._sessions.remove(session)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._close_sessions()
        await self._wait_closed()
