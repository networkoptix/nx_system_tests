# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
# This is write
# 1 ep CBW in data from host to usb request as get max lun
# 0 ep empty data from usb to host
# 1 ep data from host to usb usb request all zeroes
# 0 ep empty data from usb to host
# 2 ep empty data host to usb headers as get max lun
# 0 ep CSW in data from usb to host
# This is read
# 2 ep CBW data from host to usb request as get max lun
# 0 ep empty data from usb to host request as all zeroes
# 1 ep empty data host to usb request as all zeroes
# 0 ep data from usb to host request as all zeroes
# 1 ep empty data host to usb headers as get max lun
# 0 ep CSW in data from usb to host
import logging
from enum import Enum
from typing import Callable
from typing import Optional

from arms.usb_emulation.bulk_only_transport.packets import CommandBlockWrapper
from arms.usb_emulation.bulk_only_transport.packets import CommandStatusWrapper
from arms.usb_emulation.scsi.block_device import CommandInterrupted
from arms.usb_emulation.scsi.block_device import TargetRequest
from arms.usb_emulation.scsi.block_device import TargetResponse
from arms.usb_emulation.usb.usb_device import DataToSend

CDB_OK = 0
CDB_FAILED = 1

_logger = logging.getLogger(__name__)


class CdbState(Enum):
    WAITING_FOR_CBW = 1
    HANDLING_DATA = 2
    WAITING_FOR_CSW = 3


class DataDirection(Enum):
    OUT = 1
    IN = 2


class BBBProtocolHandle:

    cbw: Optional[CommandBlockWrapper]

    def __init__(self, command_handler: Callable[[TargetRequest], TargetResponse]):
        self.state = CdbState(CdbState.WAITING_FOR_CBW)
        self.buffer = bytearray()
        self.command_handler = command_handler
        self.status = 0

    def _handling_data_stage(
            self,
            endpoint: int,
            data: bytes,
            transfer_length: int,
            ) -> Optional[DataToSend]:
        _logger.debug(
            "Transferring to the endpoint %d, transfer length: %d", endpoint, transfer_length)
        if endpoint == DataDirection.IN.value:
            self.buffer.extend(data)
            if len(self.buffer) == self.cbw.cbw_header.d_cbw_transfer_length:
                self.state = CdbState(CdbState.WAITING_FOR_CSW)
                target_response = self.command_handler(
                    TargetRequest(
                        request=self.cbw.cbwcb,
                        buffer=bytes(self.buffer),
                        lun_number=self.cbw.cbw_header.b_cbw_lun,
                        ),
                    )
                self.status = target_response.status_code
            _logger.debug("Sending acknowledge to host")
            return DataToSend(ack_value=transfer_length, ack=True)
        else:
            if not self.buffer:
                # Before reading execute command
                response = self.command_handler(
                    TargetRequest(
                        request=self.cbw.cbwcb,
                        buffer=b'',
                        lun_number=self.cbw.cbw_header.b_cbw_lun,
                        ),
                    )
                self.status = response.status_code
                self.buffer = response.response
            self.buffer = bytearray(self.buffer)
            if self.buffer:
                packet = self.buffer[:transfer_length]
                self.buffer = self.buffer[transfer_length:]
                if not self.buffer:
                    self.state = CdbState(CdbState.WAITING_FOR_CSW)
                _logger.info("Replying with data packet to host.")
                return DataToSend(data=packet)

    def handle_data(
            self,
            data: bytes,
            endpoint: int,
            transfer_length: int,
            ) -> Optional[DataToSend]:
        # Only 2 endpoints
        if self.state.value == CdbState.WAITING_FOR_CBW.value:
            self.cbw = CommandBlockWrapper.unpack(data)
            self.state = CdbState(CdbState.HANDLING_DATA)
            _logger.info("Received BBB CBW packet: %s", str(self.cbw))
            return DataToSend(ack=True, ack_value=transfer_length)
        elif self.state.value == CdbState.HANDLING_DATA.value:
            try:
                return self._handling_data_stage(
                    endpoint=endpoint,
                    data=data,
                    transfer_length=transfer_length,
                    )
            except CommandInterrupted as interrupted:
                return_value = CommandStatusWrapper.create(
                    d_csw_tag=self.cbw.cbw_header.d_cbw_tag,
                    d_csw_data_residue=0,
                    b_csw_status=interrupted.code,
                    )
                self.reset()
                _logger.info(
                    "Request was interrupted (this may occur for valid reasons, "
                    "like allow medium removal)")
                _logger.info(
                    "Response status for tag %d is %d",
                    return_value.d_csw_tag, return_value.b_csw_status)
                return DataToSend(data=bytes(return_value))
        else:
            return_value = CommandStatusWrapper.create(
                d_csw_tag=self.cbw.cbw_header.d_cbw_tag,
                d_csw_data_residue=0,
                b_csw_status=self.status,
                )
            self.reset()
            _logger.debug(
                "Response status for tag %d is %d",
                return_value.d_csw_tag, return_value.b_csw_status)
            return DataToSend(data=bytes(return_value))

    def reset(self):
        self.state = CdbState(CdbState.WAITING_FOR_CBW)
        self.buffer = bytearray()
        self.status = 0
        self.cbw = None
