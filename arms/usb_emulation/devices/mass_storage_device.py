# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from pathlib import Path
from typing import Optional

from usb_emulation.bulk_only_transport.bulk_only_transport_protocol_handler import BBBProtocolHandle
from usb_emulation.scsi.block_device import ScsiDevice
from usb_emulation.usb.usb_descriptors import DeviceConfigurations
from usb_emulation.usb.usb_descriptors import DeviceDescriptor
from usb_emulation.usb.usb_descriptors import EndPointDescriptor
from usb_emulation.usb.usb_descriptors import InterfaceDescriptor
from usb_emulation.usb.usb_descriptors import StandardDeviceRequest
from usb_emulation.usb.usb_device import DataToSend
from usb_emulation.usb.usb_device import UsbDevice

GET_MAX_LUN_REQUEST = 0xfe

RESET_REQUEST_REQUEST = 0xff

USB_CLASS_MASS_STORAGE = 8
SCSI_INTERFACE_SUBCLASS = 0x06
BULK_INTERFACE_PROTOCOL = 0x50
USB_DIR_IN = 0x80
USB_DIR_OUT = 0
USB_ENDPOINT_XFER_BULK = 2


_logger = logging.getLogger(__name__)


class VirtualUSBMassStorage(UsbDevice):
    _device_descriptor = DeviceDescriptor(
        id_vendor=0x46f4,
        id_product=0x0001,
        bcd_device=17,
        b_device_class=0x0,
        b_device_subclass=0x0,
        b_device_protocol=0x0,
        manufacturer_name='Network Optix',
        product_name='Network Optix Virtual USB Device',
        b_max_packet_size=64,
        supports_high_speed=True,
        configurations=[
            DeviceConfigurations(
                b_configuration_value=1,
                bm_attributes=128,
                b_max_power=250,
                interfaces=[
                    InterfaceDescriptor(
                        b_interface_class=USB_CLASS_MASS_STORAGE,
                        b_interface_subclass=SCSI_INTERFACE_SUBCLASS,
                        b_interface_protocol=BULK_INTERFACE_PROTOCOL,
                        endpoints=[
                            EndPointDescriptor(
                                b_endpoint_address=USB_DIR_IN | 0x1,
                                b_interval=0xff,
                                bm_attributes=USB_ENDPOINT_XFER_BULK,
                                w_max_packet_size=512,
                                ),
                            EndPointDescriptor(
                                b_endpoint_address=USB_DIR_OUT | 0x2,
                                b_interval=0xff,
                                bm_attributes=USB_ENDPOINT_XFER_BULK,
                                w_max_packet_size=512,
                                ),
                            ],
                        descriptions=[],
                        b_alternate_settings=0,
                        ),
                    ],
                ),
            ],
        )

    def __init__(
            self,
            bus_number: int,
            device_number: int,
            usb_version: str,
            number: int,
            size_mb: int,
            root_dir: Path,
            ):
        super(VirtualUSBMassStorage, self).__init__(
            bus_number=bus_number,
            device_number=device_number,
            usb_version=usb_version,
            )
        self._root_dir = root_dir
        self._current_configuration = self._device_descriptor.configurations[0]
        self.number = number
        self.size_mb = size_mb
        block_size = self._current_configuration.interfaces[0].endpoints[0].w_max_packet_size
        self.scsi_device = ScsiDevice(
            block_size=block_size,
            luns_directory=self._root_dir / str(self.number),
            lun_size_mb=self.size_mb,
            )
        self.protocol_handler = BBBProtocolHandle(self.scsi_device.handle_cmd)

    def handle_device_specific_control(
            self,
            control_req: StandardDeviceRequest,
            ) -> Optional[DataToSend]:
        _logger.error("Handling unknown control")
        if control_req.bm_request_type == 0x21:
            # class, interface, host to device
            if control_req.b_request == RESET_REQUEST_REQUEST:
                return DataToSend(b'')
        if control_req.bm_request_type == 0xa1:
            # class, interface, device to host
            if control_req.b_request == GET_MAX_LUN_REQUEST:
                return DataToSend((self.scsi_device.get_luns_count() - 1).to_bytes(1, 'big'))

    def handle_data(self, data: bytes, endpoint: int, transfer_length: int) -> Optional[DataToSend]:
        return self.protocol_handler.handle_data(
            data=data,
            endpoint=endpoint,
            transfer_length=transfer_length,
            )

    def release(self):
        self.scsi_device.release()
