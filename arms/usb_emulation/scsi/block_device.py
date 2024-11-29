# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import math
import mmap
import os
from pathlib import Path
from typing import List
from typing import NamedTuple

from usb_emulation.scsi.scsi_protocol import ALLOW_MEDIUM_REMOVAL
from usb_emulation.scsi.scsi_protocol import INQUIRY
from usb_emulation.scsi.scsi_protocol import MODE_SENSE
from usb_emulation.scsi.scsi_protocol import READ_10
from usb_emulation.scsi.scsi_protocol import READ_6
from usb_emulation.scsi.scsi_protocol import READ_CAPACITY
from usb_emulation.scsi.scsi_protocol import REQUEST_SENSE
from usb_emulation.scsi.scsi_protocol import ReadCapacityResponse
from usb_emulation.scsi.scsi_protocol import TEST_UNIT_READY
from usb_emulation.scsi.scsi_protocol import WRITE_10
from usb_emulation.scsi.scsi_protocol import WRITE_6
from usb_emulation.scsi.scsi_protocol import create_inquiry_data
from usb_emulation.scsi.scsi_protocol import mode_sense_example
from usb_emulation.scsi.scsi_protocol import scsi_response_code_to_string
from usb_emulation.scsi.scsi_protocol import unpack_scsi_command

_logger = logging.getLogger(__name__)


class TargetRequest(NamedTuple):
    request: bytes
    buffer: bytes
    lun_number: int


class TargetResponse(NamedTuple):
    response: bytes
    status_code: int


class AddressOutOfRange(Exception):
    pass


class MediumError(Exception):
    pass


class CommandInterrupted(Exception):

    def __init__(self, code: int):
        self.code = code


class ScsiLogicalUnit:

    def __init__(
            self,
            file_path: Path,
            block_count: int,
            block_size: int,
            delete_on_close: bool = False,
            ):
        self._delete_on_close = delete_on_close
        self._file_path = file_path
        self.block_count = block_count
        self.block_size = block_size
        self._fd = None
        self._memory_map = None
        self.sense = None

    def open(self):
        self._fd = self._file_path.open('wb')
        fileno = self._fd.fileno()
        os.posix_fallocate(fileno, 0, self._get_file_size())
        _logger.info("Created file %s", str(self._file_path))
        self._fd.close()
        self._fd = self._file_path.open('r+b')
        self._memory_map = mmap.mmap(fileno, 0)

    def _get_file_size(self) -> int:
        return self.block_count * self.block_size

    def __check_address(self, address: int):
        return 0 <= address < self.block_count

    def read(self, logical_address: int, blocks_count: int) -> bytes:
        self._validate_address(logical_address, blocks_count, "Read")
        try:
            offset = logical_address * self.block_size
            data = self._memory_map[offset:offset + blocks_count * self.block_size]
        except OSError as e:
            _logger.error(
                "Error while reading address %s, block count %d",
                hex(logical_address),
                blocks_count,
                exc_info=e,
                )
            raise MediumError()
        if len(data) != blocks_count * self.block_size:
            _logger.error(
                "Error while reading address %s, block count %d. %s",
                hex(logical_address),
                blocks_count,
                f'not enough data read: {len(data)}, expected {blocks_count * self.block_size}',
                )
            raise MediumError()
        return data

    def _validate_address(self, logical_address: int, blocks_count: int, request_name: str):
        if not self.__check_address(logical_address):
            _logger.error("Write request failed, invalid address %s", hex(logical_address))
            raise AddressOutOfRange()
        if not self.__check_address(logical_address + blocks_count - 1):
            _logger.error(
                f"{request_name} request failed, last block address is invalid %s",
                hex(logical_address + blocks_count - 1),
                )
            raise AddressOutOfRange()

    def write(self, logical_address: int, data: bytes, blocks_count: int):
        self._validate_address(logical_address, blocks_count, "Write")
        expected_blocks_count = math.ceil(len(data) / self.block_size)
        if blocks_count != expected_blocks_count:
            _logger.warning(
                "Write expected blocks: %d, received: %d",
                expected_blocks_count,
                blocks_count,
                )
        try:
            offset = logical_address * self.block_size
            if offset > 0:
                self._memory_map[offset:offset + len(data)] = data
                self._memory_map.flush()
            else:
                self._memory_map[:len(data)] = data
                self._memory_map.flush()
        except OSError as e:
            _logger.error(
                "Error while writing to address %s, block count %d",
                hex(logical_address),
                blocks_count,
                exc_info=e,
                )
            raise MediumError()

    def release(self):
        self._memory_map.close()
        self._fd.close()
        if self._delete_on_close:
            self._file_path.unlink()


class ScsiDevice:
    t10_vendor_specification = "NX VIRT USB"
    product_specification_format = "NetworkOptix{size}G"
    product_revision_level = "0001"
    luns_list: List[ScsiLogicalUnit]

    def __init__(
            self,
            luns_directory: Path,
            block_size: int,
            lun_size_mb: int,
            luns_count: int = 1,
            ):
        if not luns_directory.exists():
            luns_directory.mkdir(parents=True)
        self.luns_list = [
            ScsiLogicalUnit(
                luns_directory / f'disk_{i}.raw',
                block_count=lun_size_mb * 1024 ** 2 // block_size,
                block_size=block_size,
                )
            for i in range(luns_count)
            ]
        self.size_mb = lun_size_mb
        for lun in self.luns_list:
            lun.open()

    def get_luns_count(self) -> int:
        return len(self.luns_list)

    def handle_cmd(self, request: TargetRequest) -> TargetResponse:
        lun = self.luns_list[request.lun_number]  # todo handle lun not found
        scsi_request = unpack_scsi_command(request.request)
        read_requests = [READ_6, READ_10]
        write_requests = [WRITE_6, WRITE_10]
        request_code = scsi_request.get_code()
        _logger.info(
            "Received scsi request with code %s",
            scsi_response_code_to_string(request_code),
            )
        if request_code == TEST_UNIT_READY:
            raise CommandInterrupted(0)
        elif request_code == REQUEST_SENSE:
            pass
        elif request_code in read_requests:
            _logger.info(
                "Reading from address: %s, number of blocks %d, block size %d",
                hex(scsi_request.get_logical_address()),
                scsi_request.get_number_of_blocks(),
                lun.block_size,
                )
            try:
                result = lun.read(
                    scsi_request.get_logical_address(),
                    scsi_request.get_number_of_blocks(),
                    )
                return TargetResponse(response=result, status_code=0)
            except (MediumError, AddressOutOfRange):
                raise CommandInterrupted(1)
        elif request_code in write_requests:
            _logger.info(
                "Writing to address: %s, number of blocks %d, block size %d",
                hex(scsi_request.get_logical_address()),
                scsi_request.get_number_of_blocks(),
                lun.block_size,
                )
            try:
                lun.write(
                    scsi_request.get_logical_address(),
                    request.buffer,
                    scsi_request.get_number_of_blocks(),
                    )
                return TargetResponse(response=b'', status_code=0)
            except (MediumError, AddressOutOfRange):
                raise CommandInterrupted(1)
        elif request_code == INQUIRY:
            inquiry_response = create_inquiry_data(
                t10_vendor_specification=self.t10_vendor_specification,
                product_specification=self.product_specification_format.format(size=str(self.size_mb // 1024)),
                product_revision_level=self.product_revision_level,
                )
            return TargetResponse(response=bytes(inquiry_response), status_code=0)
        elif request_code == MODE_SENSE:
            # todo mode_sense_example response
            return TargetResponse(response=mode_sense_example, status_code=0)
        elif request_code == ALLOW_MEDIUM_REMOVAL:
            raise CommandInterrupted(0)
        elif request_code == READ_CAPACITY:
            _logger.info(
                "Device maximum address: %s, block size: %d",
                hex(lun.block_count - 1),
                lun.block_size,
                )
            return TargetResponse(
                response=bytes(ReadCapacityResponse(
                    maximum_address=lun.block_count - 1,
                    block_size=lun.block_size,
                    )),
                status_code=0,
                )
        else:
            _logger.warning(
                "Unhandled scsi request %s",
                scsi_response_code_to_string(request_code),
                )

    def release(self):
        for lun in self.luns_list:
            lun.release()
