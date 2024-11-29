# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from usb_emulation.usb.usb_registry import UsbDeviceRegistry
from usb_emulation.usb_ip.usb_ip_server import UsbIpServer

registry = UsbDeviceRegistry()
registry.create_mass_storage(2)
registry.create_mass_storage(5)
registry.create_mass_storage(10)
UsbIpServer(registry).main()
