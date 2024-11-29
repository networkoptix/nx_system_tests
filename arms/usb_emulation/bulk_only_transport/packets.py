# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import struct

DEFAULT_CBW_SIGNATURE = 0x43425355

DEFAULT_CSW_SIGNATURE = 0x53425355


class CommandBlockWrapperHeader:

    format_string = b'<IIIBBB'
    size = 15
    d_cbw_signature: int  # 4 bytes
    d_cbw_tag: int  # 4 bytes
    d_cbw_transfer_length: int  # 4 bytes
    bm_cbw_flags: int  # 1 byte
    b_cbw_lun: int  # 1 byte
    b_cbwcb_length: int  # 1 byte

    def __init__(
            self,
            d_cbw_signature: int,
            d_cbw_tag: int,
            d_cbw_transfer_length: int,
            bm_cbw_flags: int,
            b_cbw_lun: int,
            b_cbwcb_length: int,
            ):
        # todo add byteshifts only for check_for_meaningfull
        self.d_cbw_signature = d_cbw_signature
        self.d_cbw_tag = d_cbw_tag
        self.d_cbw_transfer_length = d_cbw_transfer_length
        self.bm_cbw_flags = bm_cbw_flags
        self.b_cbw_lun = b_cbw_lun
        self.b_cbwcb_length = b_cbwcb_length

    @classmethod
    def unpack(cls, data: bytes):
        [
            d_cbw_signature,
            d_cbw_tag,
            d_cbw_transfer_length,
            bm_cbw_flags,
            b_cbw_lun,
            b_cbwcb_length,
            ] = struct.unpack(cls.format_string, data)
        return cls(
            d_cbw_signature=d_cbw_signature,
            d_cbw_tag=d_cbw_tag,
            d_cbw_transfer_length=d_cbw_transfer_length,
            bm_cbw_flags=bm_cbw_flags,
            b_cbw_lun=b_cbw_lun & 15,
            b_cbwcb_length=b_cbwcb_length & 31,
            )


class CommandBlockWrapper:

    cbw_header: CommandBlockWrapperHeader
    cbwcb: bytes

    def __init__(
            self,
            cbw_header: CommandBlockWrapperHeader,
            cbwcb: bytes,
            ):
        self.cbw_header = cbw_header
        self.cbwcb = cbwcb  # equals iscsi cdb

    @classmethod
    def unpack(cls, data: bytes):
        header = CommandBlockWrapperHeader.unpack(
            data[:CommandBlockWrapperHeader.size])
        cbwcb = data[header.size:header.size + header.b_cbwcb_length]
        assert header.d_cbw_signature == DEFAULT_CBW_SIGNATURE
        return cls(
            header,
            cbwcb,
            )


class CommandStatusWrapper:

    format_string = b'<IIIB'
    size = 13
    d_csw_signature: int  # 4 bytes
    d_csw_tag: int  # 4 bytes
    d_csw_data_residue: int  # 4 bytes
    b_csw_status: int  # 1 byte

    def __init__(
            self,
            d_csw_signature: int,
            d_csw_tag: int,
            d_csw_data_residue: int,
            b_csw_status: int,
            ):
        self.d_csw_signature = d_csw_signature
        self.d_csw_tag = d_csw_tag
        self.d_csw_data_residue = d_csw_data_residue
        self.b_csw_status = b_csw_status

    @classmethod
    def create(
            cls,
            d_csw_tag: int,
            d_csw_data_residue: int,
            b_csw_status: int,
            ):
        return cls(
            d_csw_signature=DEFAULT_CSW_SIGNATURE,
            d_csw_tag=d_csw_tag,
            d_csw_data_residue=d_csw_data_residue,
            b_csw_status=b_csw_status,
            )

    @classmethod
    def unpack(cls, data: bytes):
        [
            d_csw_signature,
            d_csw_tag,
            d_csw_data_residue,
            b_csw_status,
            ] = struct.unpack(cls.format_string, data)
        assert d_csw_signature == DEFAULT_CSW_SIGNATURE
        return cls(
            d_csw_signature=d_csw_signature,
            d_csw_tag=d_csw_tag,
            d_csw_data_residue=d_csw_data_residue,
            b_csw_status=b_csw_status,
            )

    def __bytes__(self):
        return struct.pack(
            self.format_string,
            self.d_csw_signature,
            self.d_csw_tag,
            self.d_csw_data_residue,
            self.b_csw_status,
            )
