# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from pathlib import Path
from typing import Set

from usb_emulation.devices.mass_storage_device import VirtualUSBMassStorage
from usb_emulation.usb.usb_device import UsbDevice


class DeviceNotFoundError(Exception):
    pass


class BadBusIdError(Exception):
    pass


class UsbDeviceRegistry:
    def __init__(
            self,
            registry_name: str = 'default',
            ):
        self._name = registry_name
        self._bus_number = 1
        self._dev_number = 1
        self._devices_by_bus: dict[tuple[int, int], UsbDevice] = {}
        self._locked_devices: Set[tuple[int, int]] = set()
        self._counter = 0

    def _increment_max_bus(self):
        if self._dev_number == 8:
            self._bus_number += 1
            self._dev_number = 1
        else:
            self._dev_number += 1
        self._counter += 1

    def create_device(self, device_type: type[UsbDevice], usb_version: str = '2.0', **kwargs):
        device = device_type(
            **{
                **dict(
                    bus_number=self._bus_number,
                    device_number=self._dev_number,
                    usb_version=usb_version,
                    ),
                **kwargs,
                },
            )
        self._devices_by_bus[(self._bus_number, self._dev_number)] = device
        self._increment_max_bus()

    def create_mass_storage(self, size_mb: int, usb_version: str = '2.0'):
        device = VirtualUSBMassStorage(
            bus_number=self._bus_number,
            device_number=self._dev_number,
            usb_version=usb_version,
            size_mb=size_mb,
            number=self._counter,
            root_dir=Path(f'/tmp/{self._name}'),
            )
        self._devices_by_bus[(self._bus_number, self._dev_number)] = device
        self._increment_max_bus()

    def fetch_by_bus_id(self, bus_id: bytes) -> UsbDevice:
        try:
            [bus_num, dev_num] = bus_id.split(b'-')
            [bus_num, dev_num] = int(bus_num), int(dev_num.rstrip(b'\x00'))
        except (ValueError, TypeError):
            raise BadBusIdError(f'Bad bus id {bus_id}')
        if (bus_num, dev_num) in self._locked_devices:
            raise DeviceNotFoundError(f"Device for bus {bus_num}-{dev_num} is locked.")
        try:
            device = self._devices_by_bus[(bus_num, dev_num)]
            self._locked_devices.add((bus_num, dev_num))
            return device
        except KeyError:
            raise DeviceNotFoundError(f"Device by bus {bus_num}-{dev_num} not found")

    def release_device(self, device: UsbDevice):
        self._locked_devices.remove((device.bus_number, device.device_number))

    def list_devices(self):
        return [value for key, value in self._devices_by_bus.items() if key not in self._locked_devices]
