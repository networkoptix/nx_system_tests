# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import struct
from abc import ABCMeta
from abc import abstractmethod

from usb_emulation.usb_ip.usbip_protocol import PrintableStruct

first_three_bits_mask = int('11100000', 2)
last_five_bit_mask = ~first_three_bits_mask

# Response examples, todo replace with real structures
mode_sense_example = (
    b'C\x00\x00\x00\x01\n\x00\x03\x00\x00\x00\x00\x80\x03\x00\x00\x05\x1e\x13\x88\x00\x10'
    b'?\x00\x00=\x80\x00\x00\x00\x00\x00\x00\x00\x00\x05\x1e\x00\x00\x00\x00\x00\x00\x00\x01h'
    b'\x00\x00\x1b\n\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x1c\x06\x00\x05\x00\x00\x00\x1c')
#
# SCSI opcodes
#
TEST_UNIT_READY = 0x00
REQUEST_SENSE = 0x03
READ_6 = 0x08
WRITE_6 = 0x0a
INQUIRY = 0x12
MODE_SENSE = 0x1a
ALLOW_MEDIUM_REMOVAL = 0x1e
READ_CAPACITY = 0x25
READ_10 = 0x28
WRITE_10 = 0x2a

SCSI_OPCODES_STRINGS = {
    TEST_UNIT_READY: "TEST UNIT READY",
    REQUEST_SENSE: "REQUEST SENSE",
    READ_6: "READ(6)",
    WRITE_6: "WRITE(6)",
    INQUIRY: "INQUIRY",
    MODE_SENSE: "MODE SENSE",
    ALLOW_MEDIUM_REMOVAL: "ALLOW MEDIUM REMOVAL",
    READ_CAPACITY: "READ CAPACITY",
    READ_10: "READ(10)",
    WRITE_10: "WRITE(10)",
    }


SAM_STAT_GOOD = 0x00
SAM_STAT_CHECK_CONDITION = 0x02
SAM_STAT_CONDITION_MET = 0x04
SAM_STAT_BUSY = 0x08
SAM_STAT_INTERMEDIATE = 0x10
SAM_STAT_INTERMEDIATE_CONDITION_MET = 0x14
SAM_STAT_RESERVATION_CONFLICT = 0x18
SAM_STAT_COMMAND_TERMINATED = 0x22  # obsolete in SAM-3
SAM_STAT_TASK_SET_FULL = 0x28
SAM_STAT_ACA_ACTIVE = 0x30
SAM_STAT_TASK_ABORTED = 0x40

#
#  SENSE KEYS
#
NO_SENSE = 0x00
RECOVERED_ERROR = 0x01
NOT_READY = 0x02
MEDIUM_ERROR = 0x03
HARDWARE_ERROR = 0x04
ILLEGAL_REQUEST = 0x05
UNIT_ATTENTION = 0x06
DATA_PROTECT = 0x07
BLANK_CHECK = 0x08
COPY_ABORTED = 0x0a
ABORTED_COMMAND = 0x0b
VOLUME_OVERFLOW = 0x0d
MISCOMPARE = 0x0e

#
# Additional Sense Code (ASC) used
#
ASC_NO_ADDED_SENSE = 0x00
ASC_INVALID_FIELD_IN_CDB = 0x24
ASC_POWERON_RESET = 0x29
ASC_NOT_SELF_CONFIGURED = 0x3e


def scsi_response_code_to_string(scsi_response_code: int) -> str:
    return SCSI_OPCODES_STRINGS.get(scsi_response_code, hex(scsi_response_code))


class BaseScsiCdb(metaclass=ABCMeta):
    opcode: int

    @abstractmethod
    def get_logical_address(self) -> int:
        pass

    @abstractmethod
    def get_number_of_blocks(self) -> int:
        pass

    def get_code(self) -> int:
        return self.opcode


class StandardScsiCdb(BaseScsiCdb):
    logical_block_address: int
    transfer_length: int

    def get_logical_address(self) -> int:
        return self.logical_block_address

    def get_number_of_blocks(self) -> int:
        return self.transfer_length


class ScsiCdb6B(PrintableStruct, StandardScsiCdb):
    format_string = b'>BBHBB'
    size = 5
    opcode: int  # 1 byte
    miscelaneous: int  # 3 bits
    logical_block_address: int  # 5 bits and then 2 bytes (LBA)
    transfer_length: int  # 1 byte
    # either transfer length or parameter list length or
    # allocation length
    control: int  # 1 byte

    def __init__(
            self,
            opcode: int,
            significant_byte: int,
            logical_block_address: int,
            transfer_length: int,
            control: int,
            ):
        self.opcode = opcode
        self.transfer_length = transfer_length
        self.control = control
        self.miscelaneous = (significant_byte & first_three_bits_mask) >> 5
        most_significant_bit = (significant_byte & last_five_bit_mask)
        self.logical_block_address = most_significant_bit << 8 + logical_block_address

    @classmethod
    def unpack(cls, data: bytes):
        [
            opcode,
            significant_byte,
            logical_block_address,
            transfer_length,
            control,
            ] = struct.unpack(cls.format_string, data)
        return cls(
            opcode=opcode,
            significant_byte=significant_byte,
            logical_block_address=logical_block_address,
            transfer_length=transfer_length,
            control=control,
            )


class ScsiCdb10B(PrintableStruct, StandardScsiCdb):
    format_string = ">BBIBHB"
    size = 10
    opcode: int  # 1 byte
    miscelaneous: int  # 3 bits
    service_action: int  # MSB, 5 bits
    logical_block_address: int  # 4 bytes (LBA)
    miscelaneous_0: int  # 1 byte
    transfer_length: int  # 2 bytes
    control: int  # 1 byte

    def __init__(
            self,
            opcode: int,
            miscelaneous_byte: int,
            logical_block_address: int,
            miscelaneous_0: int,
            transfer_length: int,
            control: int,
            ):
        self.opcode = opcode
        self.miscelaneous = (miscelaneous_byte & first_three_bits_mask) >> 5
        self.service_action = (miscelaneous_byte & last_five_bit_mask)
        self.logical_block_address = logical_block_address
        self.miscelaneous_0 = miscelaneous_0
        self.transfer_length = transfer_length
        self.control = control

    @classmethod
    def unpack(cls, data: bytes):
        [
            opcode,
            miscelaneous_byte,
            logical_block_address,
            miscelaneous_0,
            transfer_length,
            control,
            ] = struct.unpack(cls.format_string, data)
        return cls(
            opcode=opcode,
            miscelaneous_byte=miscelaneous_byte,
            logical_block_address=logical_block_address,
            miscelaneous_0=miscelaneous_0,
            transfer_length=transfer_length,
            control=control,
            )


class ScsiCdb12B(PrintableStruct, StandardScsiCdb):
    format_string = '>BBIIBB'
    opcode: int  # 1 byte
    miscelaneous: int  # 3 bits
    service_action: int  # MSB, 5 bits
    logical_block_address: int  # 4 bytes (LBA)
    transfer_length: int  # 4 bytes
    miscelaneous_0: int  # 1 byte
    control: int  # 1 byte

    def __init__(
            self,
            opcode,
            miscelaneous_byte,
            logical_block_address,
            transfer_length,
            miscelaneous_0,
            control,
            ):
        self.opcode = opcode
        self.transfer_length = transfer_length
        self.miscelaneous = (miscelaneous_byte & first_three_bits_mask) >> 5
        self.service_action = (miscelaneous_byte & last_five_bit_mask)
        self.logical_block_address = logical_block_address
        self.miscelaneous_0 = miscelaneous_0
        self.control = control

    @classmethod
    def unpack(cls, data: bytes):
        [
            opcode,
            miscelaneous_byte,
            logical_block_address,
            transfer_length,
            miscelaneous_0,
            control,
            ] = struct.unpack(cls.format_string, data)
        return cls(
            opcode=opcode,
            miscelaneous_byte=miscelaneous_byte,
            logical_block_address=logical_block_address,
            transfer_length=transfer_length,
            miscelaneous_0=miscelaneous_0,
            control=control,
            )


class ScsiCdb16B(PrintableStruct, StandardScsiCdb):
    format_string = '>BBQIBB'
    size = 16
    opcode: int  # 1 byte
    miscelaneous: int  # 1 byte
    logical_block_address: int  # 8 bytes
    transfer_length: int  # 4 bytes
    miscelaneous_0: int  # 1 byte
    control: int  # 1 byte

    def __init__(
            self,
            opcode: int,
            miscelaneous: int,
            logical_block_address: int,
            transfer_length: int,
            miscelaneous_0: int,
            control: int,
            ):
        self.opcode = opcode
        self.miscelaneous = miscelaneous
        self.logical_block_address = logical_block_address
        self.transfer_length = transfer_length
        self.miscelaneous_0 = miscelaneous_0
        self.control = control

    @classmethod
    def unpack(cls, data: bytes):
        [
            opcode,
            miscelaneous,
            logical_block_address,
            transfer_length,
            miscelaneous_0,
            control,
            ] = struct.unpack(cls.format_string, data)
        return cls(
            opcode=opcode,
            miscelaneous=miscelaneous,
            logical_block_address=logical_block_address,
            transfer_length=transfer_length,
            miscelaneous_0=miscelaneous_0,
            control=control,
            )


inquiry_data = b'\x00\x80\x04\x02\x1fsmiJetFlashTranscend 8GB   1100'


class InquiryData:
    format_string = '>BBBBBBBB8s16sI'
    # 000 stands for
    # A peripheral device having the specified peripheral device type is connected to this logical unit.
    # If the device server isunable to determine whether or not a peripheral device
    # is connected, it also shall use this peripheral qualifier. This peripheral qualifier
    # does not mean that the peripheral device connected to the logical unit is ready for access.
    peripheral_qualifier: int  # 3 bits
    # 00h - Direct access block device (e.g., magnetic disk)
    peripheral_device_type: int  # 5 bits
    # 1 for removable, 0 otherwise
    rmb: int  # first bit of 1 byte, remaining is reserved
    # 0x4 stands for SPC-2 compliance
    version: int  # 1 byte
    # Next byte starts
    # 1 for NACA supported, not on flash drive
    normal_aca: int  # 5th bit of next byte
    # 0 in out case
    hierarchical_support_bit: int  # 4th bit HISUP
    # this equals 2, less is obsolete, more is too large
    response_data_format: int  # 3-0 bits
    # byte ends
    # The ADDITIONAL LENGTH field indicates the length in bytes
    # of the remaining standard INQUIRY data.
    additional_length: int  # 1 byte
    # Next byte
    # whereas scc is supported, 0 for no supported, not in our case
    scc_supported_bit: int  # 1 bit
    # An ACC bit set to zero indicates that no access controls coordinator may
    # be addressed through this logical unit. If the SCSI target device
    # contains an access controls coordinator that may be addressed through
    # any logical unit other than the ACCESS CONTROLS well known
    # logical unit, then the ACC bit shall be set to one for LUN 0
    access_control_coordinator_bit: int  # 1 bit
    # Here bits are 10
    tpgs_field: int  # 2 bits
    # Commands like EXTENDED COPY supported
    third_party_copy_bit: int  # 1 bit
    protect_bit: int  # last 1 bit, bits 2, 1 are reserved
    # byte end
    # Next byte
    # '0b01101001'
    enclosed_services: int  # 6-th bit, 5-th is vendor specific,
    # 7-th is reserved
    multiport_bit: int  # 4-th bit, all remaining reserved
    # byte end
    cmdqueu: int  # 1st bit, other in byte reserved
    t10_vendor_specification: bytes  # eight bytes of left-aligned ASCII
    product_specification: bytes  # s sixteen bytes of left-aligned ASCII data
    product_revision_level: int  # 4 bytes

    def __init__(
            self,
            peripheral_qualifier: int,
            peripheral_device_type: int,
            rmb: int,
            version: int,
            normal_aca: int,
            hierarchical_support_bit: int,
            response_data_format: int,
            additional_length: int,
            scc_supported_bit: int,
            access_control_coordinator_bit: int,
            tpgs_field: int,
            third_party_copy_bit: int,
            protect_bit: int,
            enclosed_services: int,
            multiport_bit: int,
            cmdqueu: int,
            t10_vendor_specification: bytes,
            product_specification: bytes,
            product_revision_level: int,
            ):
        self.peripheral_qualifier = peripheral_qualifier
        self.peripheral_device_type = peripheral_device_type
        self.rmb = rmb
        self.version = version
        self.normal_aca = normal_aca
        self.hierarchical_support_bit = hierarchical_support_bit
        self.response_data_format = response_data_format
        self.additional_length = additional_length
        self.scc_supported_bit = scc_supported_bit
        self.access_control_coordinator_bit = access_control_coordinator_bit
        self.tpgs_field = tpgs_field
        self.third_party_copy_bit = third_party_copy_bit
        self.protect_bit = protect_bit
        self.enclosed_services = enclosed_services
        self.multiport_bit = multiport_bit
        self.cmdqueu = cmdqueu
        self.t10_vendor_specification = t10_vendor_specification
        self.product_specification = product_specification
        self.product_revision_level = product_revision_level

    def __bytes__(self) -> bytes:
        peripheral_byte: int = self._pack_peripheral_byte()
        rmb_byte: int = self._pack_rmb()
        version: int = self.version
        third_byte: int = self._pack_third_byte()
        additional_length: int = self.additional_length
        fifth_byte: int = self._pack_fifth_byte()
        sixth_byte: int = self._pack_sixth_byte()
        cmdqueu: int = self._pack_cmdqueue()
        t10_vendor_specification: bytes = self.t10_vendor_specification
        product_specification: bytes = self.product_specification
        product_revision_level: int = self.product_revision_level
        return struct.pack(
            self.format_string,
            peripheral_byte,
            rmb_byte,
            version,
            third_byte,
            additional_length,
            fifth_byte,
            sixth_byte,
            cmdqueu,
            t10_vendor_specification,
            product_specification,
            product_revision_level,
            )

    @classmethod
    def unpack(cls, data: bytes):
        # NOTE: broader parameters are not supported
        [
            peripheral_byte,
            rmb_byte,
            version,
            third_byte,
            additional_length,
            fifth_byte,
            sixth_byte,
            cmdqueu,
            t10_vendor_specification,
            product_specification,
            product_revision_level,
            ] = struct.unpack(cls.format_string, data)
        [
            peripheral_qualifier,
            peripheral_device_type,
            ] = cls._unpack_peripheral_byte(peripheral_byte)
        rmb = cls._unpack_rmb(rmb_byte)
        [
            normal_aca,
            hierarchical_support_bit,
            response_data_format,
            ] = cls._unpack_third_byte(third_byte)
        [
            scc_supported_bit,
            access_control_coordinator_bit,
            tpgs_field,
            third_party_copy_bit,
            protect_bit,
            ] = cls._unpack_fifth_byte(fifth_byte)
        [enclosed_services, multiport_bit] = cls._unpack_sixth_byte(sixth_byte)
        cmdqueu = cls._unpack_cmdqueu(cmdqueu)
        return cls(
            peripheral_qualifier=peripheral_qualifier,
            peripheral_device_type=peripheral_device_type,
            rmb=rmb,
            version=version,
            normal_aca=normal_aca,
            hierarchical_support_bit=hierarchical_support_bit,
            response_data_format=response_data_format,
            additional_length=additional_length,
            scc_supported_bit=scc_supported_bit,
            access_control_coordinator_bit=access_control_coordinator_bit,
            tpgs_field=tpgs_field,
            third_party_copy_bit=third_party_copy_bit,
            protect_bit=protect_bit,
            enclosed_services=enclosed_services,
            multiport_bit=multiport_bit,
            cmdqueu=cmdqueu,
            t10_vendor_specification=t10_vendor_specification,
            product_specification=product_specification,
            product_revision_level=product_revision_level,
            )

    @staticmethod
    def _unpack_peripheral_byte(value: int) -> tuple[int, int]:
        peripheral_qualifier = (value & first_three_bits_mask) >> 5
        peripheral_device_type = value & last_five_bit_mask
        return peripheral_qualifier, peripheral_device_type

    def _pack_peripheral_byte(self) -> int:
        return (self.peripheral_qualifier << 5) | self.peripheral_device_type

    @staticmethod
    def _unpack_rmb(value: int) -> int:
        return value >> 7

    def _pack_rmb(self) -> int:
        return self.rmb << 7

    @staticmethod
    def _unpack_third_byte(value: int) -> tuple[int, int, int]:
        normal_aca = (value & 32) >> 5
        hierarchical_support_bit = (value & 16) >> 4
        response_data_format = value & 15
        return normal_aca, hierarchical_support_bit, response_data_format

    def _pack_third_byte(self) -> int:
        result = 0
        result |= self.normal_aca << 5
        result |= self.hierarchical_support_bit << 4
        result |= self.response_data_format
        return result

    @staticmethod
    def _unpack_fifth_byte(value: int) -> tuple[int, int, int, int, int]:
        protect_bit = value & 1
        third_party_copy_bit = (value & 8) >> 3
        tpgs_field = (value & 48) >> 4
        access_control_coordinator_bit = (value & 64) >> 6
        scc_supported_bit = (value & 128) >> 7
        return (
            scc_supported_bit,
            access_control_coordinator_bit,
            tpgs_field,
            third_party_copy_bit,
            protect_bit,
            )

    def _pack_fifth_byte(self) -> int:
        result = self.protect_bit
        result |= self.third_party_copy_bit << 3
        result |= self.tpgs_field << 4
        result |= self.access_control_coordinator_bit << 6
        result |= self.scc_supported_bit << 7
        return result

    @staticmethod
    def _unpack_sixth_byte(value: int) -> tuple[int, int]:
        enclosed_services = (value & 64) >> 6
        multiport_bit = (value & 16) >> 4
        return enclosed_services, multiport_bit

    def _pack_sixth_byte(self) -> int:
        return (self.enclosed_services << 6) | (self.multiport_bit << 4)

    @staticmethod
    def _unpack_cmdqueu(value: int) -> int:
        return (value & 2) >> 1

    def _pack_cmdqueue(self) -> int:
        return self.cmdqueu << 1


class ReadCapacityResponse:

    def __init__(self, maximum_address: int, block_size: int):
        self.maximum_address = maximum_address
        self.block_size = block_size

    def __bytes__(self) -> bytes:
        try:
            max_address = self.maximum_address.to_bytes(4, 'big')
        except OverflowError:
            max_address = b'\xff\xff\xff\xff'
        return max_address + self.block_size.to_bytes(4, 'big')

    @classmethod
    def unpack(cls, data: bytes):
        maximum_address = int.from_bytes(data[:4], 'big')
        block_size = int.from_bytes(data[4:8], 'big')
        return cls(
            maximum_address=maximum_address,
            block_size=block_size,
            )


def create_inquiry_data(
        t10_vendor_specification: str,
        product_specification: str,
        product_revision_level: str,
        ) -> InquiryData:
    t10_vendor_specification = t10_vendor_specification.encode('ascii')[:8]
    product_specification = product_specification.encode('ascii')[:16]
    product_revision_level = product_revision_level.encode('ascii')[:4]
    return InquiryData(
        access_control_coordinator_bit=1,
        additional_length=31,
        cmdqueu=0,
        multiport_bit=0,
        normal_aca=0,
        peripheral_device_type=0,
        peripheral_qualifier=0,
        t10_vendor_specification=t10_vendor_specification,
        product_specification=product_specification,
        tpgs_field=3,
        version=4,
        protect_bit=1,
        scc_supported_bit=0,
        third_party_copy_bit=0,
        response_data_format=2,
        hierarchical_support_bit=0,
        enclosed_services=1,
        product_revision_level=int.from_bytes(product_revision_level, 'big'),
        rmb=1,
        )


class SenseResponse:
    format_string = '>BBBIBIBBBBH'
    error_code: int  # 1 byte
    segment_number: int  # 1 byte
    sense_key: int  # 1 byte
    information: int  # 4 bytes
    additional_sense_length: int  # 1 byte
    command_specific_information: int  # 4 bytes
    additional_sense_code: int  # 1 byte
    additional_sense_code_qualifier: int  # 1 byte
    field_replaceable_unit_code: int  # 1 byte
    multibit_param: int  # 1 bytes, SKV, C/D
    # See: https://docs.oracle.com/cd/F12888_01/ACSIR/scsi_commands.htm#CIHFJJBF
    field_pointer: int  # 2 bytes

    def __init__(
            self,
            error_code: int,
            segment_number: int,
            sense_key: int,
            information: int,
            additional_sense_length: int,
            command_specific_information: int,
            additional_sense_code: int,
            additional_sense_code_qualifier: int,
            field_replaceable_unit_code: int,
            multibit_param: int,
            field_pointer: int,
            ):
        self.error_code = error_code
        self.segment_number = segment_number
        self.sense_key = sense_key
        self.information = information
        self.additional_sense_length = additional_sense_length
        self.command_specific_information = command_specific_information
        self.additional_sense_code = additional_sense_code
        self.additional_sense_code_qualifier = additional_sense_code_qualifier
        self.field_replaceable_unit_code = field_replaceable_unit_code
        self.multibit_param = multibit_param
        self.field_pointer = field_pointer

    @classmethod
    def unpack(cls, data: bytes):  # todo in usbip on fail of request return only header with status
        # todo make this class a header and make variadic parsing fom file
        [
            error_code,
            segment_number,
            sense_key,
            information,
            additional_sense_length,
            command_specific_information,
            additional_sense_code,
            additional_sense_code_qualifier,
            field_replaceable_unit_code,
            multibit_param,
            field_pointer,
            ] = struct.unpack(cls.format_string, data)
        return cls(
            error_code=error_code,
            segment_number=segment_number,
            sense_key=sense_key,
            information=information,
            additional_sense_length=additional_sense_length,
            command_specific_information=command_specific_information,
            additional_sense_code=additional_sense_code,
            additional_sense_code_qualifier=additional_sense_code_qualifier,
            field_replaceable_unit_code=field_replaceable_unit_code,
            multibit_param=multibit_param,
            field_pointer=field_pointer,
            )

    def __bytes__(self) -> bytes:
        return struct.pack(
            self.format_string,
            self.error_code,
            self.segment_number,
            self.sense_key,
            self.information,
            self.additional_sense_length,
            self.command_specific_information,
            self.additional_sense_code,
            self.additional_sense_code_qualifier,
            self.field_replaceable_unit_code,
            self.multibit_param,
            self.field_pointer,
            )


def extract_command_length(data: bytes) -> int:
    command = data[0]
    size = (command & first_three_bits_mask) >> 5
    if size == 0:
        return 6
    elif size == 1:
        return 10
    elif size == 2:
        return 10
    elif size == 4:
        return 16
    elif size == 5:
        return 12
    else:
        raise RuntimeError("Unknown command")


def unpack_scsi_command(data: bytes) -> BaseScsiCdb:
    commands = {
        6: ScsiCdb6B,
        10: ScsiCdb10B,
        12: ScsiCdb12B,
        16: ScsiCdb16B,
        }
    cmd_length = extract_command_length(data)
    return commands[cmd_length].unpack(data)
