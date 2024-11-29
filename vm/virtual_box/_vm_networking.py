# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/

from functools import lru_cache

from vm.hypervisor import PciAddress
from vm.hypervisor import PciAddressPart
from vm.virtual_box._vboxmanage import vbox_manage_list

# NIC 1 is used via port forwarding for:
# - remote OS setup,
# - working with remote filesystem,
# - installing Mediaserver.
# Others are used to combine VMs into internal networks. These are unplugged before every test.
INTERNAL_NIC_INDICES = [2, 3, 4]

# PCI slots for devices are hard-coded in VirtualBox sources.
# See: https://www.virtualbox.org/pipermail/vbox-dev/2013-July/011657.html
# See: https://www.virtualbox.org/browser/vbox/trunk/src/VBox/Main/src-client/BusAssignmentManager.cpp?rev=70238#L83  # NOQA
# PCI paths are sequence of device-function pairs,
# the last is adapter slot numbers, the others are bridges.
nic_pci_slots: dict[int, PciAddress] = {
    1: PciAddress(PciAddressPart(3, 0)),
    2: PciAddress(PciAddressPart(8, 0)),
    3: PciAddress(PciAddressPart(9, 0)),
    4: PciAddress(PciAddressPart(10, 0)),
    5: PciAddress(PciAddressPart(16, 0)),
    6: PciAddress(PciAddressPart(17, 0)),
    7: PciAddress(PciAddressPart(18, 0)),
    8: PciAddress(PciAddressPart(19, 0)),
    }

nic_slots: dict[PciAddress, int] = {
    pci_address: slot for slot, pci_address in nic_pci_slots.items()}


@lru_cache()
def host_network_interfaces():
    """Needed to validate bridged adapter name."""
    interfaces = vbox_manage_list('bridgedifs')
    return [interface['Name'] for interface in interfaces]


def bandwidth_group(nic_index):
    return 'network{}'.format(nic_index)
