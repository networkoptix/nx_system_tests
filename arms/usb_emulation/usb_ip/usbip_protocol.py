# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import struct
from typing import List

_logger = logging.getLogger(__name__)


USBIP_COMMAND_RET_SUBMIT = 0x3
USBIP_COMMAND_RET_UNLINK = 0x00000004
USBIP_COMMAND_REQ_UNLINK = 0x2
USBIP_COMMAND_ATTACH_CODE = 0x8003
USBIP_COMMAND_DEVLIST_CODE = 0x8005
USBIP_COMMAND_USBMIT = 0x00000001
USBIP_COMMAND_RET_DEVLIST_CODE = 0x0005

USBIP_BUS_ID_SIZE = 32
USBIP_DEFAULT_VERSION = 273


# Usb ip statuses
# See https://elixir.bootlin.com/linux/v4.19-rc2/source/include/uapi/linux/usbip.h#L14
USB_IP_OK = 0x00
# OK
USB_IP_NA = 0x01
# Device requested for import is not available
USB_IP_DEVICE_USED = 0x02
# USB IP is unusable because of a fatal error.
USB_IP_DEVICE_ERROR = 0x03
USB_IP_NO_DEVICE = 0x04
USB_IP_GENERIC_ERROR = 0x05


class CanBeFormatted:
    format_string: bytes
    size: int


class PrintableStruct:

    def __str__(self):
        result = []
        skip = {
            '__annotations__',
            '__dict__',
            '__doc__',
            '__module__',
            '__weakref__',
            '__slotnames__',
            }
        for attr_name in dir(self):
            if attr_name in skip:
                continue
            attr_value = getattr(self, attr_name)
            if not callable(attr_value):
                result.append(f'{attr_name}={attr_value}')
        return (
            f'<{self.__class__.__name__}>\n'
            + '\n'.join(result)
            + f'\n</{self.__class__.__name__}>'
            )


class USBIPHeader(CanBeFormatted, PrintableStruct):
    format_string = '>HHI'
    size = 8
    version: int  # 2 byte
    command: int  # 2 bytes
    status: int   # 4 byte

    def __init__(
            self,
            version: int,
            command: int,
            status: int,
            ):
        self.version = version
        self.command = command
        self.status = status

    def __bytes__(self) -> bytes:
        return struct.pack(self.format_string, self.version, self.command, self.status)

    @classmethod
    def unpack(cls, data: bytes):
        version, command, status = struct.unpack(cls.format_string, data)
        return cls(
            version=version,
            command=command,
            status=status,
            )


def usb_ip_ret_submit_header(status: int = USB_IP_OK) -> USBIPHeader:
    return USBIPHeader(
        version=USBIP_DEFAULT_VERSION,
        command=USBIP_COMMAND_RET_SUBMIT,
        status=status,
        )


def usb_ip_rep_import_header(status: int = USB_IP_OK) -> USBIPHeader:
    return usb_ip_ret_submit_header(status)


def usb_ip_dev_list_header() -> USBIPHeader:
    return USBIPHeader(
        version=USBIP_DEFAULT_VERSION,
        command=USBIP_COMMAND_RET_DEVLIST_CODE,
        status=0,
        )


class USBInterface(CanBeFormatted):

    format_string = '>BBBB'
    size = 4
    b_interface_class: int
    b_interface_sub_class: int
    b_interface_protocol: int
    align: int = 0

    def __init__(
            self,
            b_interface_class: int,
            b_interface_sub_class: int,
            b_interface_protocol: int,
            ):
        self.b_interface_class = b_interface_class
        self.b_interface_sub_class = b_interface_sub_class
        self.b_interface_protocol = b_interface_protocol

    def __bytes__(self) -> bytes:
        return struct.pack(
            self.format_string,
            self.b_interface_class,
            self.b_interface_sub_class,
            self.b_interface_protocol,
            self.align,
            )

    @classmethod
    def unpack(cls, data: bytes):
        [
            b_interface_class,
            b_interface_sub_class,
            b_interface_protocol,
            ] = struct.unpack(cls.format_string, data)
        return cls(
            b_interface_class=b_interface_class,
            b_interface_sub_class=b_interface_sub_class,
            b_interface_protocol=b_interface_protocol,
            )


class USBIPRETSubmitHeader(CanBeFormatted, PrintableStruct):
    format_string = '>IIIIIIIIIIQ'
    size = 48
    command: int  # 4 bytes
    seqnum: int  # 4 bytes
    devid: int  # 4 bytes
    direction: int  # 4 bytes
    ep: int  # 4 bytes
    status: int  # 4 bytes
    actual_length: int  # 4 bytes
    start_frame: int  # 4 bytes
    number_of_packets: int  # 4 bytes
    error_count: int  # 4 bytes
    setup: int  # 8 bytes

    def __init__(
            self,
            command: int,
            seqnum: int,
            devid: int,
            direction: int,
            ep: int,
            status: int,
            actual_length: int,
            start_frame: int,
            number_of_packets: int,
            error_count: int,
            setup: int,
            ):
        self.command = command
        self.seqnum = seqnum
        self.devid = devid
        self.direction = direction
        self.ep = ep
        self.status = status
        self.actual_length = actual_length
        self.start_frame = start_frame
        self.number_of_packets = number_of_packets
        self.error_count = error_count
        self.setup = setup

    def __bytes__(self) -> bytes:
        data = (
            self.command,
            self.seqnum,
            self.devid,
            self.direction,
            self.ep,
            self.status,
            self.actual_length,
            self.start_frame,
            self.number_of_packets,
            self.error_count,
            self.setup,
            )
        return struct.pack(
            self.format_string,
            *data,
            )

    @classmethod
    def unpack(cls, data: bytes) -> 'USBIPRETSubmitHeader':
        [
            command,
            seqnum,
            devid,
            direction,
            ep,
            status,
            actual_length,
            start_frame,
            number_of_packets,
            error_count,
            setup,
            ] = struct.unpack(cls.format_string, data)
        return cls(
            command=command,
            seqnum=seqnum,
            devid=devid,
            direction=direction,
            ep=ep,
            status=status,
            actual_length=actual_length,
            start_frame=start_frame,
            number_of_packets=number_of_packets,
            error_count=error_count,
            setup=setup,
            )


class USBIPRETSubmit(PrintableStruct):
    header: USBIPRETSubmitHeader
    data: bytes

    def __init__(self, header: USBIPRETSubmitHeader, data: bytes):
        self.header = header
        self.data = data

    def __bytes__(self) -> bytes:
        return bytes(self.header) + self.data

    @classmethod
    def create_ack(cls, seqnum: int, ack_value: int):
        # ACK for Mass storage protocol
        # actual_length = 31, could not find any reference,
        # the value was obtained from the real traffic
        header = USBIPRETSubmitHeader(
            command=USBIP_COMMAND_RET_SUBMIT,
            seqnum=seqnum,
            ep=0,
            status=0,
            devid=0,
            error_count=0,
            direction=0,
            setup=0,
            actual_length=ack_value,
            start_frame=0x0,
            number_of_packets=0x0,
            )
        return USBIPRETSubmit(header=header, data=b'')

    @classmethod
    def create_response(
            cls,
            seqnum: int,
            endpoint: int,
            status: int,
            data: bytes,
            ) -> 'USBIPRETSubmit':
        header = USBIPRETSubmitHeader(
            command=USBIP_COMMAND_RET_SUBMIT,
            seqnum=seqnum,
            ep=endpoint,
            status=status,
            devid=0,
            error_count=0,
            direction=0,
            setup=0,
            actual_length=len(data),
            start_frame=0x0,
            number_of_packets=0x0,
            )
        return USBIPRETSubmit(header=header, data=data)

    @property
    def setup(self) -> bytes:
        return self.header.setup.to_bytes(8, 'big')


class USBIPCMDSubmitHeader(CanBeFormatted, PrintableStruct):

    format_string = '>IIIIIIIIIIQ'
    size = 48
    command: int  # 4 bytes
    seqnum: int  # 4 bytes
    devid: int  # 4 bytes
    direction: int  # 4 bytes
    ep: int  # 4 bytes
    transfer_flags: int  # 4 bytes
    transfer_buffer_length: int  # 4 bytes
    start_frame: int  # 4 bytes
    number_of_packets: int  # 4 bytes
    interval: int  # 4 bytes
    setup: int  # 8 bytes

    def __init__(
            self,
            command: int,
            seqnum: int,
            devid: int,
            direction: int,
            ep: int,
            transfer_flags: int,
            transfer_buffer_length: int,
            start_frame: int,
            number_of_packets: int,
            interval: int,
            setup: int,
            ):
        self.command = command
        self.seqnum = seqnum
        self.devid = devid
        self.direction = direction
        self.ep = ep
        self.transfer_flags = transfer_flags
        self.transfer_buffer_length = transfer_buffer_length
        self.start_frame = start_frame
        self.number_of_packets = number_of_packets
        self.interval = interval
        self.setup = setup

    def __bytes__(self) -> bytes:
        data_to_pack = (
            self.command,
            self.seqnum,
            self.devid,
            self.direction,
            self.ep,
            self.transfer_flags,
            self.transfer_buffer_length,
            self.start_frame,
            self.number_of_packets,
            self.interval,
            self.setup,
            )
        return struct.pack(self.format_string, *data_to_pack)

    @classmethod
    def unpack(cls, data: bytes) -> 'USBIPCMDSubmitHeader':
        [
            command,
            seqnum,
            devid,
            direction,
            ep,
            transfer_flags,
            transfer_buffer_length,
            start_frame,
            number_of_packets,
            interval,
            setup,
            ] = struct.unpack(cls.format_string, data)
        return cls(
            command=command,
            seqnum=seqnum,
            devid=devid,
            direction=direction,
            ep=ep,
            transfer_flags=transfer_flags,
            transfer_buffer_length=transfer_buffer_length,
            start_frame=start_frame,
            number_of_packets=number_of_packets,
            interval=interval,
            setup=setup,
            )


class EmptyHeader(Exception):
    pass


class EmptyBody(Exception):

    def __init__(self, seqnum: int):
        self.seqnum = seqnum


class USBIPCMDSubmit(PrintableStruct):
    header: USBIPCMDSubmitHeader
    data: bytes

    def __init__(self, header: USBIPCMDSubmitHeader, data: bytes):
        self.header = header
        self.data = data

    def __bytes__(self) -> bytes:
        return bytes(self.header) + self.data

    @property
    def ep(self) -> int:
        return self.header.ep

    @property
    def seqnum(self) -> int:
        return self.header.seqnum

    @property
    def setup(self) -> bytes:
        return self.header.setup.to_bytes(8, 'big')


class USBIPDeviceInfo(CanBeFormatted, PrintableStruct):
    # Common device info for
    # OPREP_IMPORT and OPREP_DEV_LIST
    size = 56
    format_string = '>32sIIIHHHBBBBBB'
    bus_id: bytes  # 32 bytes
    bus_num: int  # 4 bytes
    dev_num: int  # 4 bytes
    speed: int  # 4 bytes
    id_vendor: int  # 2 bytes
    id_product: int  # 2 bytes
    bcd_device: int  # 2 bytes
    b_device_class: int  # 1 byte
    b_device_subclass: int  # 1 bytes
    b_device_protocol: int  # 1 bytes
    b_configuration_value: int  # 1 bytes
    b_num_configurations: int  # 1 bytes
    b_num_interfaces: int = 0  # 1 bytes

    def __init__(
            self,
            bus_id: bytes,
            bus_num: int,
            dev_num: int,
            speed: int,
            id_vendor: int,
            id_product: int,
            bcd_device: int,
            b_device_class: int,
            b_device_subclass: int,
            b_device_protocol: int,
            b_configuration_value: int,
            b_num_configurations: int,
            b_num_interfaces: int = 0,
            ):
        self.bus_id = bus_id
        self.bus_num = bus_num
        self.dev_num = dev_num
        self.speed = speed
        self.id_vendor = id_vendor
        self.id_product = id_product
        self.bcd_device = bcd_device
        self.b_device_class = b_device_class
        self.b_device_subclass = b_device_subclass
        self.b_device_protocol = b_device_protocol
        self.b_configuration_value = b_configuration_value
        self.b_num_configurations = b_num_configurations
        self.b_num_interfaces = b_num_interfaces

    def __bytes__(self) -> bytes:
        return struct.pack(
            self.format_string,
            self.bus_id,
            self.bus_num,
            self.dev_num,
            self.speed,
            self.id_vendor,
            self.id_product,
            self.bcd_device,
            self.b_device_class,
            self.b_device_subclass,
            self.b_device_protocol,
            self.b_configuration_value,
            self.b_num_configurations,
            self.b_num_interfaces,
            )


class OPREPDevListDevice:

    usb_path: bytes  # 256 bytes
    device_info: USBIPDeviceInfo
    interfaces: List[USBInterface]

    def __init__(
            self,
            usb_path: str,
            device_info: USBIPDeviceInfo,
            interfaces: List[USBInterface],
            ):
        self.usb_path = usb_path.encode()
        self.device_info = device_info
        self.interfaces = interfaces
        self.device_info.b_num_interfaces = len(interfaces)

    def __bytes__(self) -> bytes:
        result = struct.pack('>256s', self.usb_path)
        result += bytes(self.device_info)
        for interface in self.interfaces:
            result += bytes(interface)
        return result


class OPREPDevList:
    base: USBIPHeader
    n_exported_device: int  # 32 bytes
    devices: List[OPREPDevListDevice]

    def __init__(self, devices: List[OPREPDevListDevice]):
        self.base = usb_ip_dev_list_header()
        self.devices = devices
        self.n_exported_device = len(self.devices)

    def __bytes__(self) -> bytes:
        result: bytes = bytes(self.base)
        result += self.n_exported_device.to_bytes(4, 'big')
        for device in self.devices:
            result += bytes(device)
        return result


class OPREPImport(PrintableStruct):
    base: USBIPHeader
    usb_path: str  # 256 bytes
    device_info: USBIPDeviceInfo

    def __init__(self, usb_path: str, device_info: USBIPDeviceInfo):
        self.base = usb_ip_rep_import_header()
        self.usb_path = usb_path
        self.device_info = device_info

    def __bytes__(self):
        result = bytes(self.base)
        result += struct.pack('>256s', self.usb_path.encode())
        result += bytes(self.device_info)
        return result


class OPREQImport:
    base: USBIPHeader
    bus_id: bytes  # 32 bytes string

    def __init__(self, header: USBIPHeader, bus_id: bytes):
        self.base = header
        self.bus_id = bus_id


class USBIPRETUnlink(CanBeFormatted):
    format_string = '>IIIIII'
    size = 6
    command: int = USBIP_COMMAND_RET_UNLINK  # 32 bytes
    seqnum: int  # 4 bytes
    devid: int  # 4 bytes
    direction: int  # 4 bytes
    ep: int  # 4 bytes
    unlink_seqnum: int  # 4 bytes

    def __init__(
            self,
            seqnum: int,  # 4 bytes
            devid: int,  # 4 bytes
            direction: int,  # 4 bytes
            ep: int,  # 4 bytes
            unlink_seqnum: int,  # 4 bytes
            command: int = USBIP_COMMAND_RET_UNLINK,  # 32 bytes
            ):
        self.seqnum = seqnum
        self.devid = devid
        self.direction = direction
        self.ep = ep
        self.unlink_seqnum = unlink_seqnum
        self.command = command

    def __bytes__(self) -> bytes:
        return struct.pack(
            self.format_string,
            self.command,
            self.seqnum,
            self.devid,
            self.direction,
            self.ep,
            self.unlink_seqnum,
            )

    @classmethod
    def unpack(cls, data: bytes) -> 'USBIPRETUnlink':
        [
            command,
            seqnum,
            devid,
            direction,
            ep,
            unlink_seqnum,
            ] = struct.unpack(cls.format_string, data)
        return cls(
            command=command,
            seqnum=seqnum,
            devid=devid,
            direction=direction,
            ep=ep,
            unlink_seqnum=unlink_seqnum,
            )


class USBIPUnlinkReqHeader(CanBeFormatted):
    size = 48
    format_string = '>IIIIIIIIIIQ'
    command: int = USBIP_COMMAND_REQ_UNLINK  # 4 bytes
    seqnum: int  # 4 bytes
    devid: int = 0x2  # 4 bytes
    direction: int  # 4 bytes
    ep: int  # 4 bytes
    transfer_flags: int  # 4 bytes
    transfer_buffer_length: int  # 4 bytes
    start_frame: int  # 4 bytes
    number_of_packets: int  # 4 bytes
    interval: int  # 4 bytes
    setup: int  # 8 bytes

    def __init__(
            self,
            seqnum: int,
            direction: int,
            ep: int,
            transfer_flags: int,
            transfer_buffer_length: int,
            start_frame: int,
            number_of_packets: int,
            interval: int,
            setup: int,
            devid: int = 0x2,
            command: int = USBIP_COMMAND_REQ_UNLINK,
            ):
        self.seqnum = seqnum
        self.direction = direction
        self.ep = ep
        self.transfer_flags = transfer_flags
        self.transfer_buffer_length = transfer_buffer_length
        self.start_frame = start_frame
        self.number_of_packets = number_of_packets
        self.interval = interval
        self.setup = setup
        self.devid = devid
        self.command = command

    def __bytes__(self) -> bytes:
        return struct.pack(
            self.format_string,
            self.command,
            self.seqnum,
            self.devid,
            self.direction,
            self.ep,
            self.transfer_flags,
            self.transfer_buffer_length,
            self.start_frame,
            self.number_of_packets,
            self.interval,
            self.setup,
            )

    @classmethod
    def unpack(cls, data: bytes) -> 'USBIPUnlinkReqHeader':
        [
            command,
            seqnum,
            devid,
            direction,
            ep,
            transfer_flags,
            transfer_buffer_length,
            start_frame,
            number_of_packets,
            interval,
            setup,
            ] = struct.unpack(cls.format_string, data)
        return cls(
            command=command,
            seqnum=seqnum,
            devid=devid,
            direction=direction,
            ep=ep,
            transfer_flags=transfer_flags,
            transfer_buffer_length=transfer_buffer_length,
            start_frame=start_frame,
            number_of_packets=number_of_packets,
            interval=interval,
            setup=setup,
            )


class USBIPUnlinkReq:
    header: USBIPUnlinkReqHeader
    data: bytes

    def __init__(self, header: USBIPUnlinkReqHeader, data: bytes):
        self.header = header
        self.data = data

    def __bytes__(self) -> bytes:
        return bytes(self.header) + self.data
