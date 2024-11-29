# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
# This module contains definition
# of standard USB descriptors
# but contains no info on their parsing
import struct
from typing import List
from typing import Optional
from typing import Protocol
from typing import Union

from arms.usb_emulation.usb_ip.usbip_protocol import PrintableStruct

DESCRIPTOR_TYPE_DEVICE = 0x1
DESCRIPTOR_TYPE_CONFIGURATION = 0x2
DESCRIPTOR_TYPE_STRING = 0x3
DESCRIPTOR_TYPE_INTERFACE = 0x4
DESCRIPTOR_TYPE_ENDPOINT = 0x5
DESCRIPTOR_TYPE_DEVICE_QUALIFIER = 0x6
DESCRIPTOR_TYPE_OTHER_SPEED_CONFIGURATION = 0x7
DESCRIPTOR_TYPE_INTERFACE_POWER = 0x8

DATA_TRANSFER_HOST_TO_DEVICE = 0
DATA_TRANSFER_DEVICE_TO_HOST = 1


def parse_usb_version(usb_version: str) -> tuple[int, int, int]:
    [major, minor, *sub] = usb_version.split('.')
    major = int(major)
    minor = int(minor)
    if not sub:
        return major, minor, 0
    [sub] = sub
    return major, minor, int(sub)


def usb_version_hex(
        major_version: int,
        minor_version: int,
        sub_version: int,
        ):
    return (major_version << 8) + (minor_version << 4) + sub_version


class Serializable(Protocol):

    def __bytes__(self) -> bytes:
        pass


class EndPointDescriptor:
    format_string = '>BBBBHB'
    size = struct.calcsize(format_string)
    b_length: int = size  # 1 byte
    b_descriptor_type: int = DESCRIPTOR_TYPE_ENDPOINT  # 1 byte
    b_endpoint_address: int = 0x81  # 1 byte
    bm_attributes: int = 0x3  # 1 byte
    w_max_packet_size: int = 0x8000  # 2 bytes, little endian
    b_interval: int = 0x0A  # 1 byte

    def __init__(
            self,
            b_endpoint_address: int = 0x81,
            bm_attributes: int = 0x3,
            w_max_packet_size: int = 0x8000,
            b_interval: int = 0x0A,
            ):
        self.b_endpoint_address = b_endpoint_address
        self.bm_attributes = bm_attributes
        self.w_max_packet_size = w_max_packet_size
        self.b_interval = b_interval

    def __bytes__(self):
        w_max_packet_size = int.from_bytes(
            self.w_max_packet_size.to_bytes(2, 'big'), 'little')
        return struct.pack(
            self.format_string,
            self.b_length,
            self.b_descriptor_type,
            self.b_endpoint_address,
            self.bm_attributes,
            w_max_packet_size,
            self.b_interval,
            )

    @classmethod
    def unpack(cls, data: bytes) -> 'EndPointDescriptor':
        [
            b_length,
            b_descriptor_type,
            b_endpoint_address,
            bm_attributes,
            w_max_packet_size,
            b_interval,
            ] = struct.unpack(cls.format_string, data)
        # WARNING: Despite the whole endpoint descriptor
        # is big endian, w_max_packed_size is little endian.
        w_max_packet_size = int.from_bytes(
            w_max_packet_size.to_bytes(2, 'big'), 'little')
        instance = cls.__new__(cls)
        instance.b_length = b_length
        instance.b_descriptor_type = b_descriptor_type
        instance.b_endpoint_address = b_endpoint_address
        instance.bm_attributes = bm_attributes
        instance.w_max_packet_size = w_max_packet_size
        instance.b_interval = b_interval
        return instance


class InterfaceDescriptor(PrintableStruct):
    format_string = '>BBBBBBBBB'
    size = struct.calcsize(format_string)
    b_length: int = size  # 1 bytes
    b_descriptor_type: int = DESCRIPTOR_TYPE_INTERFACE  # 1 bytes
    b_interface_number: int = 0  # 1 byte
    b_alternate_settings: int = 0  # 1 byte
    b_num_endpoints: int = 1  # 1 byte
    b_interface_class: int = 3  # 1 byte
    b_interface_subclass: int = 1  # 1 byte
    b_interface_protocol: int = 2  # 1 byte
    i_interface: int = 0  # 1 byte
    interface_string: Optional[str] = None
    endpoints: List[EndPointDescriptor]
    descriptions: List[Serializable]

    def __init__(
            self,
            endpoints: List[EndPointDescriptor],
            descriptions: List[Serializable],
            b_interface_number: int = 0,
            b_alternate_settings: int = 0,
            b_interface_class: int = 3,
            b_interface_subclass: int = 1,
            b_interface_protocol: int = 2,
            interface_string: Optional[str] = None,
            ):
        self.endpoints = endpoints
        self.descriptions = descriptions
        self.b_interface_number = b_interface_number
        self.b_alternate_settings = b_alternate_settings
        self.b_num_endpoints = len(self.endpoints)
        self.b_interface_class = b_interface_class
        self.b_interface_subclass = b_interface_subclass
        self.b_interface_protocol = b_interface_protocol
        self.interface_string = interface_string

    def __bytes__(self) -> bytes:
        return struct.pack(
            self.format_string,
            self.b_length,
            self.b_descriptor_type,
            self.b_interface_number,
            self.b_alternate_settings,
            self.b_num_endpoints,
            self.b_interface_class,
            self.b_interface_subclass,
            self.b_interface_protocol,
            self.i_interface,
            )

    def total_size(self) -> int:
        result = self.size
        result += EndPointDescriptor.size * len(self.endpoints)
        for description in self.descriptions:
            result += len(bytes(description))
        return result

    @classmethod
    def unpack(cls, data: bytes) -> 'InterfaceDescriptor':
        [
            b_length,
            b_descriptor_type,
            b_interface_number,
            b_alternate_settings,
            b_num_endpoints,
            b_interface_class,
            b_interface_subclass,
            b_interface_protocol,
            i_interface,
            ] = struct.unpack(cls.format_string, data)
        interface_descriptor = cls.__new__(cls)
        interface_descriptor.b_length = b_length
        interface_descriptor.b_descriptor_type = b_descriptor_type
        interface_descriptor.b_interface_number = b_interface_number
        interface_descriptor.b_alternate_settings = b_alternate_settings
        interface_descriptor.b_num_endpoints = b_num_endpoints
        interface_descriptor.b_interface_class = b_interface_class
        interface_descriptor.b_interface_subclass = b_interface_subclass
        interface_descriptor.b_interface_protocol = b_interface_protocol
        interface_descriptor.i_interface = i_interface
        return interface_descriptor


class StringDescriptor(PrintableStruct):
    format_string = '>BB'
    size = struct.calcsize(format_string)
    b_length: int  # 1 byte
    b_descriptor_type: int = DESCRIPTOR_TYPE_STRING  # 1 byte
    data: bytes

    def __init__(self, line: str):
        data = line.encode('utf-16')
        self.b_length = len(data) + self.size
        self.data = data

    def __bytes__(self):
        return struct.pack(self.format_string, self.b_length, self.b_descriptor_type) + self.data

    @classmethod
    def unpack(cls, data: bytes) -> 'StringDescriptor':
        struct_header = data[:cls.size]
        string_descriptor = cls.__new__(cls)
        [b_length, b_descriptor_type] = struct.unpack(cls.format_string, struct_header)
        string_descriptor.b_length = b_length
        string_descriptor.b_descriptor_type = b_descriptor_type
        string_descriptor.data = data[cls.size:]
        return string_descriptor


class StringDescriptorZero:
    format_string = '>BBH'
    b_length: int = struct.calcsize(format_string)  # 1 byte
    b_descriptor_type: int = DESCRIPTOR_TYPE_STRING  # 1 byte
    w_lang_id_0: int = 0x0409  # 2 bytes

    def __bytes__(self) -> bytes:
        return struct.pack(
            self.format_string,
            self.b_length,
            self.b_descriptor_type,
            self.w_lang_id_0,
            )


class DeviceConfigurations:
    format_string = '>BBHBBBBB'
    size = struct.calcsize(format_string)
    b_length: int = size  # 1 byte
    b_descriptor_type: int = DESCRIPTOR_TYPE_CONFIGURATION  # 1 byte
    w_total_length: int  # 2 bytes
    b_num_interfaces: int  # 1 byte
    b_configuration_value: int  # 1 byte
    i_configuration: int = 0  # 1 byte
    configuration_string: Optional[str] = None
    bm_attributes: int = 0x80  # 1 byte
    b_max_power: int = 0x32  # 1 byte
    interfaces: List[InterfaceDescriptor]

    def __init__(
            self,
            b_configuration_value: int,
            interfaces: List[InterfaceDescriptor],
            bm_attributes: int = 0x80,
            b_max_power: int = 0x32,
            configuration_string: Optional[str] = None,
            ):
        self.interfaces = interfaces
        self.w_total_length = self._calc_total_length()
        self.b_num_interfaces = len(self.interfaces)
        self.b_configuration_value = b_configuration_value
        self.configuration_string = configuration_string
        self.bm_attributes = bm_attributes
        self.b_max_power = b_max_power

    def _calc_total_length(self) -> int:
        result = self.size
        for interface in self.interfaces:
            result += interface.total_size()
        return result

    def __bytes__(self) -> bytes:
        result = struct.pack(
            self.format_string,
            self.b_length,
            self.b_descriptor_type,
            self.w_total_length,
            self.b_num_interfaces,
            self.b_configuration_value,
            self.i_configuration,
            self.bm_attributes,
            self.b_max_power,
            )
        for interface in self.interfaces:
            result += bytes(interface)
            for description in interface.descriptions:
                result += bytes(description)
            for endpoint in interface.endpoints:
                result += bytes(endpoint)
        return result

    @classmethod
    def unpack(cls, data: bytes) -> 'DeviceConfigurations':
        if len(data) == cls.size:
            return cls.default_unpack(data)

    @classmethod
    def default_unpack(cls, data: bytes) -> 'DeviceConfigurations':
        [
            b_length,
            b_descriptor_type,
            w_total_length,
            b_num_interfaces,
            b_configuration_value,
            i_configuration,
            bm_attributes,
            b_max_power,
            ] = struct.unpack(cls.format_string, data)
        device_configurations = cls.__new__(cls)
        device_configurations.b_length = b_length
        device_configurations.b_descriptor_type = b_descriptor_type
        device_configurations.w_total_length = w_total_length
        device_configurations.b_num_interfaces = b_num_interfaces
        device_configurations.b_configuration_value = b_configuration_value
        device_configurations.i_configuration = i_configuration
        device_configurations.bm_attributes = bm_attributes
        device_configurations.b_max_power = b_max_power
        return device_configurations


class DeviceQualifier(PrintableStruct):
    format_string = '>BBHBBBBBB'
    b_length: int = struct.calcsize(format_string)
    b_descriptor_type: int = DESCRIPTOR_TYPE_DEVICE_QUALIFIER
    bcd_usb: int
    b_device_class: int
    b_device_subclass: int
    b_device_protocol: int
    b_max_packet_size_0: int
    b_num_configurations: int
    b_reserved: int = 0

    def __init__(
            self,
            bcd_usb: int,
            b_device_class: int,
            b_device_subclass: int,
            b_device_protocol: int,
            b_max_packet_size_0: int,
            b_num_configurations: int,
            ):
        self.bcd_usb = bcd_usb
        self.b_device_class = b_device_class
        self.b_device_subclass = b_device_subclass
        self.b_device_protocol = b_device_protocol
        self.b_max_packet_size_0 = b_max_packet_size_0
        self.b_num_configurations = b_num_configurations

    def __bytes__(self) -> bytes:
        return struct.pack(
            self.format_string,
            self.b_length,
            self.b_descriptor_type,
            self.bcd_usb,
            self.b_device_class,
            self.b_device_subclass,
            self.b_device_protocol,
            self.b_max_packet_size_0,
            self.b_num_configurations,
            self.b_reserved,
            )


class DeviceDescriptor(PrintableStruct):
    format_string = '>BBHBBBBHHHBBBB'
    b_length: int = struct.calcsize(format_string)  # 1 byte
    b_descriptor_type: int = DESCRIPTOR_TYPE_DEVICE  # 1 byte
    bcd_usb: int = 0x0200  # 2 bytes
    b_device_class: int  # 1 byte
    b_device_subclass: int  # 1 byte
    b_device_protocol: int  # 1 byte
    b_max_packet_size: int  # 1 byte
    id_vendor: int  # 2 bytes
    id_product: int  # 2 bytes
    bcd_device: int  # 2 bytes
    i_manufacturer: int = 0  # 1 byte
    i_product: int = 0  # 1 byte
    i_serial_number: int = 0  # 1 byte
    b_num_configurations: int  # 1 byte
    manufacturer_name: Optional[str] = None
    product_name: Optional[str] = None
    serial_number_string: Optional[str] = None
    configurations: List[DeviceConfigurations]
    string_descriptors: List[Union[StringDescriptor, StringDescriptorZero]]

    def __init__(
            self,
            b_device_class: int,
            b_device_subclass: int,
            b_device_protocol: int,
            b_max_packet_size: int,
            id_vendor: int,
            id_product: int,
            bcd_device: int,
            configurations: List[DeviceConfigurations],
            usb_version: Optional[str] = None,
            manufacturer_name: Optional[str] = None,
            product_name: Optional[str] = None,
            serial_number_string: Optional[str] = None,
            supports_high_speed: bool = False,
            ):
        if usb_version is not None:
            self.set_usb_version(usb_version)
        self.b_device_class = b_device_class
        self.b_device_subclass = b_device_subclass
        self.b_device_protocol = b_device_protocol
        self.b_max_packet_size = b_max_packet_size
        self.id_vendor = id_vendor
        self.id_product = id_product
        self.bcd_device = bcd_device
        self.configurations = configurations
        self.string_descriptors = []
        self.b_num_configurations = len(self.configurations)
        self.manufacturer_name = manufacturer_name
        self.product_name = product_name
        self.serial_number_string = serial_number_string
        self.supports_high_speed = supports_high_speed

    def __bytes__(self) -> bytes:
        return struct.pack(
            self.format_string,
            self.b_length,
            self.b_descriptor_type,
            int.from_bytes(self.bcd_usb.to_bytes(2, 'big'), 'little'),
            self.b_device_class,
            self.b_device_subclass,
            self.b_device_protocol,
            self.b_max_packet_size,
            self.id_vendor,
            self.id_product,
            self.bcd_device,
            self.i_manufacturer,
            self.i_product,
            self.i_serial_number,
            self.b_num_configurations,
            )

    def set_usb_version(self, usb_version: str):
        self.bcd_usb = usb_version_hex(*parse_usb_version(usb_version))

    def set_serial_number(self, serial_number: str):
        self.serial_number_string = serial_number

    def process_string_descriptors(self):
        if self.manufacturer_name is not None:
            self.string_descriptors.append(StringDescriptor(self.manufacturer_name))
            self.i_manufacturer = len(self.string_descriptors)
        if self.product_name is not None:
            self.string_descriptors.append(StringDescriptor(self.product_name))
            self.i_product = len(self.string_descriptors)
        if self.serial_number_string is not None:
            self.string_descriptors.append(StringDescriptor(self.serial_number_string))
            self.i_serial_number = len(self.string_descriptors)
        for configuration in self.configurations:
            if configuration.configuration_string is not None:
                self.string_descriptors.append(
                    StringDescriptor(configuration.configuration_string))
                configuration.i_configuration = len(self.string_descriptors)
            for interface in configuration.interfaces:
                if interface.interface_string is None:
                    continue
                self.string_descriptors.append(
                    StringDescriptor(interface.interface_string))
                interface.i_interface = len(self.string_descriptors)
        if self.string_descriptors:
            self.string_descriptors.insert(0, StringDescriptorZero())

    @classmethod
    def unpack(cls, data: bytes) -> 'DeviceDescriptor':
        [
            b_length,
            b_descriptor_type,
            bcd_usb,
            b_device_class,
            b_device_subclass,
            b_device_protocol,
            b_max_packet_size,
            id_vendor,
            id_product,
            bcd_device,
            i_manufacturer,
            i_product,
            i_serial_number,
            b_num_configurations,
            ] = struct.unpack(cls.format_string, data)
        parsed_descriptor = cls.__new__(cls)
        parsed_descriptor.b_length = b_length
        parsed_descriptor.b_descriptor_type = b_descriptor_type
        parsed_descriptor.bcd_usb = int.from_bytes(bcd_usb.to_bytes(2, 'big'), 'little')
        parsed_descriptor.b_device_class = b_device_class
        parsed_descriptor.b_device_subclass = b_device_subclass
        parsed_descriptor.b_device_protocol = b_device_protocol
        parsed_descriptor.b_max_packet_size = b_max_packet_size
        parsed_descriptor.id_vendor = id_vendor
        parsed_descriptor.id_product = id_product
        parsed_descriptor.bcd_device = bcd_device
        parsed_descriptor.i_manufacturer = i_manufacturer
        parsed_descriptor.i_product = i_product
        parsed_descriptor.i_serial_number = i_serial_number
        parsed_descriptor.b_num_configurations = b_num_configurations
        return parsed_descriptor

    def qualifier(self):
        return DeviceQualifier(
            b_device_class=self.b_device_class,
            b_device_protocol=self.b_device_protocol,
            b_device_subclass=self.b_device_subclass,
            b_num_configurations=self.b_num_configurations,
            b_max_packet_size_0=self.b_max_packet_size,
            bcd_usb=self.bcd_usb,
            )


class StandardDeviceRequest:
    format_string = '>BBHHH'
    size = struct.calcsize(format_string)
    bm_request_type: int  # 1 byte
    b_request: int  # 1 byte
    w_value: int  # 2 byte
    w_index: int  # 2 byte
    w_length: int  # 2 byte, little endian

    def __init__(
            self,
            bm_request_type: int,
            b_request: int,
            w_value: int,
            w_index: int,
            w_length: int,
            ):
        self.bm_request_type = bm_request_type
        self.b_request = b_request
        self.w_value = w_value
        self.w_index = w_index
        self.w_length = w_length

    @classmethod
    def unpack(cls, data: bytes) -> 'StandardDeviceRequest':
        [bm_request_type, b_request, w_value, w_index, w_length] = struct.unpack(
            cls.format_string,
            data,
            )
        return cls(
            bm_request_type=bm_request_type,
            b_request=b_request,
            w_value=w_value,
            w_index=w_index,
            w_length=int.from_bytes(w_length.to_bytes(2, 'big'), 'little'),
            )

    def data_transfer_direction(self):
        # last bit (7)
        # 0 = Host-to-device
        # 1 = Device-to-host
        # 10000000B - device to host
        return (self.bm_request_type & 128) >> 7

    def data_transfer_type(self):
        # Bits 6-5
        # 0 for standard
        # 1 for class
        # 2 for vendor
        # 3 for reserved
        return (self.bm_request_type & 96) >> 5

    def recipient(self):
        # Bits 0-4
        # 0 for device
        # 1 for interface
        # 2 or endpoint
        # 3 for other
        # 4..31 - reserved
        return self.bm_request_type & 15

    def descriptor_index(self) -> int:
        return self.w_value >> 8  # low byte

    def descriptor_type(self) -> int:
        return self.w_value & 255  # high byte

    def __str__(self) -> str:
        return (
            f'bmRequestType={self.bm_request_type!r}; '
            f'bRequest={self.b_request!r}; '
            f'wLength={self.w_length!r}; '
            f'wValue={self.w_value!r}; '
            f'wIndex={self.w_index!r}; '
            )
