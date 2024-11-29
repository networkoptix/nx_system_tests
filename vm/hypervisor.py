# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from __future__ import annotations

import logging
from abc import ABCMeta
from abc import abstractmethod
from pathlib import Path
from typing import Mapping
from typing import NamedTuple
from typing import Sequence
from typing import Tuple
from typing import TypedDict


class HypervisorError(Exception):
    pass


class VmNotFound(Exception):
    """Error to handle outside; part of the interface; legitimate outcome."""


class DiskInUse(Exception):
    pass


class PciAddressPart(NamedTuple):

    # The full PCI notation is:
    # <domain:0x4>:<bus:0x2>:<device:0x2>.<function:1x>
    # It does look like industrial standard and there is no link to the "root" standard exists
    # However, examples are plenty:
    # https://libvirt.org/pci-addresses.html#simple-cases
    # https://wiki.xenproject.org/wiki/Bus:Device.Function_(BDF)_Notation
    #
    # The "domain" field is nearly always is zero.
    # It often gets omitted output of commands like "lspci".
    #
    # The "bus" field we do not use yet.

    device: int = 0
    function: int = 0

    def __str__(self):
        return f"{self.device:02x}.{self.function:x}"


class PciAddress(Tuple[PciAddressPart]):

    def __new__(cls, *parts: Sequence[PciAddressPart]):
        if not len(parts):
            raise RuntimeError("PCIAddress must contain at least one instance of PciAddressPart")
        for part in parts:
            assert isinstance(part, PciAddressPart)
        return super(PciAddress, cls).__new__(cls, parts)

    def __str__(self):
        return "pci:0000:" + "/".join(map(str, self))


class PortMap(TypedDict):
    tcp: Mapping[int, int]
    udp: Mapping[int, int]


class Vm(metaclass=ABCMeta):

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def purge(self):
        pass

    @abstractmethod
    def reset(self):
        pass

    @abstractmethod
    def power_on(self):
        pass

    @abstractmethod
    def power_off(self):
        pass

    @abstractmethod
    def connect_cable(self, nic_id: PciAddress):
        pass

    @abstractmethod
    def disconnect_cable(self, nic_id: PciAddress):
        pass

    @abstractmethod
    def plug_bridged(self, host_nic_name: str) -> PciAddress:
        pass

    @abstractmethod
    def os_name(self) -> str:
        pass

    @abstractmethod
    def plug_internal(self, network_name: str) -> PciAddress:
        pass

    @abstractmethod
    def limit_bandwidth(self, speed_limit_kbit: int):
        pass

    @abstractmethod
    def add_disk(self, controller_type: str, size_mb: int):
        pass

    @abstractmethod
    def add_disk_limited(self, controller_type: str, size_mb: int, speed_limit_mbs: int):
        pass

    @abstractmethod
    def copy_logs(self, destination_dir: Path):
        pass

    @abstractmethod
    def shutdown(self, timeout_sec=30):
        pass

    @abstractmethod
    def save_as_plugin_snapshot(self, parent_snapshot_uri: str, plugin_id: str):
        pass

    @abstractmethod
    def save_as_base_snapshot(self, os_name: str, metadata: Mapping[str, str]) -> str:
        pass

    @abstractmethod
    def take_screenshot(self, file):
        pass

    @abstractmethod
    def set_screen_mode(self, width: int, height: int, color_depth: int):
        pass

    @abstractmethod
    def ip_address(self) -> str:
        pass

    @abstractmethod
    def port_map(self) -> PortMap:
        pass


class Hypervisor:

    @abstractmethod
    def get_base_snapshot_uri(self, os_name: str) -> str:
        pass


class VMScreenCannotSetMode(Exception):
    pass


_logger = logging.getLogger(__name__)
