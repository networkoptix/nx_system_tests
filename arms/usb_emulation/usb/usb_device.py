# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import copy
import logging
from abc import ABCMeta
from abc import abstractmethod
from typing import NamedTuple
from typing import Optional
from uuid import uuid4

from arms.usb_emulation.usb.usb_descriptors import DESCRIPTOR_TYPE_CONFIGURATION
from arms.usb_emulation.usb.usb_descriptors import DESCRIPTOR_TYPE_DEVICE
from arms.usb_emulation.usb.usb_descriptors import DESCRIPTOR_TYPE_DEVICE_QUALIFIER
from arms.usb_emulation.usb.usb_descriptors import DESCRIPTOR_TYPE_STRING
from arms.usb_emulation.usb.usb_descriptors import DeviceDescriptor
from arms.usb_emulation.usb.usb_descriptors import StandardDeviceRequest
from arms.usb_emulation.usb_ip.usbip_protocol import OPREPDevListDevice
from arms.usb_emulation.usb_ip.usbip_protocol import OPREPImport
from arms.usb_emulation.usb_ip.usbip_protocol import USBIPDeviceInfo
from arms.usb_emulation.usb_ip.usbip_protocol import USBInterface
from arms.usb_emulation.usb_ip.usbip_protocol import USB_IP_DEVICE_USED
from arms.usb_emulation.usb_ip.usbip_protocol import USB_IP_NA
from arms.usb_emulation.usb_ip.usbip_protocol import USB_IP_OK

USB_REQUEST_SET_CONFIGURATION = 0x09
USB_REQUEST_GET_STATUS = 0x00
USB_REQUEST_GET_DESCRIPTOR = 0x06
USB_CONTROL_REQUEST_TYPE_HOST = 0x80
USB_CONTROL_REQUEST_TYPE_USB = 0x00

_logger = logging.getLogger(__name__)


def create_serial_number() -> str:
    return str(uuid4()).replace('-', '')[:12]


class DataToSend(NamedTuple):
    data: bytes = b''
    status: int = USB_IP_OK
    ack: bool = False
    ack_value: int = 0


class BaseConfig:
    pass


class UsbDevice(metaclass=ABCMeta):

    _device_descriptor: DeviceDescriptor

    def __init__(
            self,
            bus_number: int,
            device_number: int,
            usb_version: str,
            ):
        self.bus_number = bus_number
        self.device_number = device_number
        self.bus_id = f'{bus_number}-{self.device_number}'.encode()
        self._sys_path_prefix = '/sys/devices/pci0000:00/0000:00:01.2'
        self._usb_sys_path = self._generate_usb_path(int(usb_version[0]))
        self._device_descriptor = copy.deepcopy(self.__class__._device_descriptor)
        self._device_descriptor.set_usb_version(usb_version)
        self._device_descriptor.set_serial_number(create_serial_number())
        self._device_descriptor.process_string_descriptors()

    def _generate_usb_path(self, usb_major_version: int):
        return (
            f'{self._sys_path_prefix}/usb{usb_major_version}/'
            f'{self.bus_number}-{self.device_number}'
            )

    @abstractmethod
    def handle_device_specific_control(
            self,
            control_req: StandardDeviceRequest,
            ) -> Optional[DataToSend]:
        pass

    @abstractmethod
    def handle_data(self, data: bytes, endpoint: int, transfer_length: int) -> Optional[DataToSend]:
        pass

    @abstractmethod
    def release(self):
        pass

    def get_usbip_op_rep_import(self) -> OPREPImport:
        return OPREPImport(
            usb_path=self._usb_sys_path,
            device_info=self.get_usb_ip_dev_info(),
            )

    def get_usb_ip_dev_info(self) -> USBIPDeviceInfo:
        speed = 2
        if self._device_descriptor.supports_high_speed:
            speed = 3
        return USBIPDeviceInfo(
            bus_id=self.bus_id,
            bus_num=self.bus_number,
            dev_num=self.device_number,
            speed=speed,
            id_vendor=self._device_descriptor.id_vendor,
            id_product=self._device_descriptor.id_product,
            bcd_device=self._device_descriptor.bcd_device,
            b_device_class=self._device_descriptor.b_device_class,
            b_device_subclass=self._device_descriptor.b_device_subclass,
            b_device_protocol=self._device_descriptor.b_device_protocol,
            b_num_configurations=self._device_descriptor.b_num_configurations,
            b_configuration_value=self._device_descriptor.configurations[0].b_configuration_value,
            b_num_interfaces=self._device_descriptor.configurations[0].b_num_interfaces,
            )

    def get_usbip_op_rep_dev_list_device(self) -> OPREPDevListDevice:
        interfaces = self._device_descriptor.configurations[0].interfaces
        return OPREPDevListDevice(
            usb_path=self._usb_sys_path,
            device_info=self.get_usb_ip_dev_info(),
            interfaces=[
                USBInterface(
                    b_interface_class=interface.b_interface_class,
                    b_interface_sub_class=interface.b_interface_subclass,
                    b_interface_protocol=interface.b_interface_protocol,
                    )
                for interface in interfaces
                ],
            )

    def handle_get_descriptor(self, control_request: StandardDeviceRequest) -> Optional[DataToSend]:
        _logger.info("Handling GetDescriptor usb command.")
        index = control_request.descriptor_index()
        descriptor_type = control_request.descriptor_type()
        if descriptor_type == DESCRIPTOR_TYPE_DEVICE:
            _logger.info("Return device descriptor: %s", str(self._device_descriptor))
            return DataToSend(data=bytes(self._device_descriptor)[:control_request.w_length])
        elif descriptor_type == DESCRIPTOR_TYPE_CONFIGURATION:
            # todo make configuration single for device descriptor
            configuration = self._device_descriptor.configurations[0]
            _logger.info("Return device configuration %s", str(configuration))
            return DataToSend(
                data=bytes(configuration)[:control_request.w_length])
        elif descriptor_type == DESCRIPTOR_TYPE_STRING:  # string
            try:
                descriptor = self._device_descriptor.string_descriptors[index]
                return DataToSend(data=bytes(descriptor)[:control_request.w_length])
            except IndexError:
                available_indices = 'no available string indices'
                n = len(self._device_descriptor.string_descriptors)
                if n > 0:
                    available_indices = f'available string indices: {0}-{n}'
                _logger.error("Invalid index %d, %s", index, available_indices)

        elif descriptor_type == DESCRIPTOR_TYPE_DEVICE_QUALIFIER:
            if self._device_descriptor.supports_high_speed:
                device_qualifier = self._device_descriptor.qualifier()
                _logger.info("Returning device qualifier descriptor %s ", str(device_qualifier))
                return DataToSend(
                    data=bytes(device_qualifier)[:control_request.w_length],
                    status=USB_IP_OK)
            # For a full speed device return error
        else:
            _logger.info("Unknown or device specific descriptor code.")

    def handle_usb_control(self, control_request: StandardDeviceRequest) -> Optional[DataToSend]:
        result = None
        _logger.info("Handling control request: %s", str(control_request))
        if control_request.bm_request_type == USB_CONTROL_REQUEST_TYPE_HOST:
            if control_request.b_request == USB_REQUEST_GET_DESCRIPTOR:
                result = self.handle_get_descriptor(control_request)
            if control_request.b_request == USB_REQUEST_GET_STATUS:  # Get STATUS
                return DataToSend(data=b'\x01\x00', status=USB_IP_DEVICE_USED)

        elif control_request.bm_request_type == USB_CONTROL_REQUEST_TYPE_USB:
            if control_request.b_request == USB_REQUEST_SET_CONFIGURATION:
                _logger.info("Handling set configuration. For most devices empty reply is sufficient.")
                return DataToSend(data=b'')

        if result is not None:
            return result
        _logger.info("Handling device specific control request.")
        unknown_control_handle_result = self.handle_device_specific_control(control_request)
        if unknown_control_handle_result is not None:
            return unknown_control_handle_result
        _logger.error("Don't know how to process control request '%s', sending error", str(control_request))
        return DataToSend(data=b'', status=USB_IP_NA)

    def __str__(self):
        return f"USB {self.bus_number}-{self.device_number}"
