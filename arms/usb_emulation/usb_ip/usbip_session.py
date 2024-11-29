# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from socket import socket
from typing import BinaryIO
from typing import List
from typing import Optional

from usb_emulation.usb.usb_descriptors import StandardDeviceRequest
from usb_emulation.usb.usb_device import UsbDevice
from usb_emulation.usb.usb_registry import BadBusIdError
from usb_emulation.usb.usb_registry import DeviceNotFoundError
from usb_emulation.usb.usb_registry import UsbDeviceRegistry
from usb_emulation.usb_ip.usbip_protocol import EmptyBody
from usb_emulation.usb_ip.usbip_protocol import EmptyHeader
from usb_emulation.usb_ip.usbip_protocol import OPREPDevList
from usb_emulation.usb_ip.usbip_protocol import OPREQImport
from usb_emulation.usb_ip.usbip_protocol import USBIPCMDSubmit
from usb_emulation.usb_ip.usbip_protocol import USBIPCMDSubmitHeader
from usb_emulation.usb_ip.usbip_protocol import USBIPHeader
from usb_emulation.usb_ip.usbip_protocol import USBIPRETSubmit
from usb_emulation.usb_ip.usbip_protocol import USBIP_BUS_ID_SIZE
from usb_emulation.usb_ip.usbip_protocol import USBIP_COMMAND_ATTACH_CODE
from usb_emulation.usb_ip.usbip_protocol import USBIP_COMMAND_DEVLIST_CODE
from usb_emulation.usb_ip.usbip_protocol import USB_IP_DEVICE_USED
from usb_emulation.usb_ip.usbip_protocol import USB_IP_GENERIC_ERROR
from usb_emulation.usb_ip.usbip_protocol import usb_ip_rep_import_header

_logger = logging.getLogger(__name__)


class ConnectionClosed(Exception):
    pass


def usb_device_list_to_op_rep_list(usb_devices: List[UsbDevice]) -> OPREPDevList:
    devices = []
    _logger.info("Show available devices")
    for index, usb_device in enumerate(usb_devices):
        devices.append(usb_device.get_usbip_op_rep_dev_list_device())
        _logger.info("Available device %d: %s", index + 1, str(usb_device))
    return OPREPDevList(devices=devices)


class UsbIpConnection:
    def __init__(
            self,
            file: BinaryIO,
            device: UsbDevice,
            registry: UsbDeviceRegistry,
            ):
        self._file = file
        self._device = device
        self._registry = registry

    def send_usb_response(
            self,
            seqnum: int,
            usb_res: bytes,
            endpoint: int = 0,
            status: int = 0,
            ):
        self._file.write(
            bytes(
                USBIPRETSubmit.create_response(
                    seqnum=seqnum,
                    status=status,
                    endpoint=endpoint,
                    data=usb_res),
                ),
            )
        self._file.flush()
        _logger.debug("Send response for seq number: %d", seqnum)

    def send_usb_ack(
            self,
            usb_req: USBIPCMDSubmit,
            ack_value: int,
            ):
        self._file.write(
            bytes(
                USBIPRETSubmit.create_ack(
                    seqnum=usb_req.seqnum,
                    ack_value=ack_value,
                    ),
                ),
            )
        self._file.flush()
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

    def handle_usbip_submit(self):
        try:
            result = self._file.read(USBIPCMDSubmitHeader.size)
            if not result:
                raise EmptyHeader()
            header = USBIPCMDSubmitHeader.unpack(result)
            data = b''
            if header.direction == 0 and header.transfer_buffer_length > 0:
                data = self._file.read(header.transfer_buffer_length)
                if len(data) < header.transfer_buffer_length:
                    _logger.error(
                        "Received incorrect size for request body, expected length=%d, actual length=%d",
                        len(data),
                        )
                    _logger.info("Header: %s", str(header))
                    raise EmptyBody(header.seqnum)
            cmd = USBIPCMDSubmit(header=header, data=data)
        except EmptyBody as e:
            self.send_usb_response(e.seqnum, b'', status=USB_IP_GENERIC_ERROR)
            raise ConnectionClosed()
        except EmptyHeader:
            raise ConnectionClosed()
        control_request = StandardDeviceRequest.unpack(cmd.setup)
        self.handle_usb_request(cmd, control_request)

    def release(self):
        self._registry.release_device(self._device)


class UsbIpSession:
    def __init__(
            self,
            connection: socket,
            usb_device_registry: UsbDeviceRegistry,
            ):
        self._file: BinaryIO = connection.makefile('rwb')
        self._registry = usb_device_registry
        self._established_connection: Optional[UsbIpConnection] = None

    def _get_usb_ip_header(self):
        data = self._file.read(USBIPHeader.size)
        if not data:
            return None
        return USBIPHeader.unpack(data)

    def _handle_device_list(self):
        _logger.info("Handle device list")
        self._file.write(
            bytes(
                usb_device_list_to_op_rep_list(
                    self._registry.list_devices(),
                    ),
                ),
            )
        self._file.flush()

    def _handle_attach(self, import_request: OPREQImport):
        _logger.info("Attaching device")
        try:
            usb_device = self._registry.fetch_by_bus_id(import_request.bus_id)
            _logger.info("Obtained usb device %", str(usb_device))
        except DeviceNotFoundError:
            self._file.write(
                bytes(usb_ip_rep_import_header(status=USB_IP_DEVICE_USED)))
            self._file.flush()
            raise ConnectionClosed()
        except BadBusIdError:
            self._file.write(
                bytes(usb_ip_rep_import_header(status=USB_IP_GENERIC_ERROR)))
            self._file.flush()
            raise ConnectionClosed()
        self._file.write(bytes(usb_device.get_usbip_op_rep_import()))
        self._file.flush()
        self._established_connection = UsbIpConnection(
            file=self._file,
            device=usb_device,
            registry=self._registry,
            )

    def _dispatch_usb_ip_header(self, header: USBIPHeader):
        if header.command == USBIP_COMMAND_DEVLIST_CODE:
            self._handle_device_list()
        elif header.command == USBIP_COMMAND_ATTACH_CODE:
            import_request = OPREQImport(header, self._file.read(USBIP_BUS_ID_SIZE))
            self._handle_attach(import_request)

    def listen(self):
        while True:
            try:
                if self._established_connection is None:
                    usbip_header = self._get_usb_ip_header()
                    if usbip_header is None:
                        break
                    self._dispatch_usb_ip_header(usbip_header)
                else:
                    self._established_connection.handle_usbip_submit()
            except ConnectionClosed:
                _logger.info("Closing connection.")
                break
        if self._established_connection is not None:
            self._established_connection.release()
