# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import asyncio
import logging
import signal
from contextlib import suppress

from arms.usb_emulation.usb.usb_registry import UsbDeviceRegistry
from arms.usb_emulation.usb_ip.async_usbip_server import UsbIpSessionsManager
from arms.usb_emulation.usb_ip.async_usbip_server import UsbIpStreamServer

logging.basicConfig(level=logging.INFO)

_logger = logging.getLogger(__name__)


async def main():
    registry = UsbDeviceRegistry()
    for _ in range(2):
        registry.create_mass_storage(2)

    server = UsbIpStreamServer()
    manager = UsbIpSessionsManager(registry)
    running_event_loop = asyncio.get_running_loop()
    async with manager:
        async with server.serve(manager.schedule_session) as tcp_server:
            running_event_loop.add_signal_handler(signal.SIGINT, tcp_server.close)
            running_event_loop.add_signal_handler(signal.SIGTERM, tcp_server.close)
            with suppress(asyncio.CancelledError):
                await tcp_server.serve_forever()
            _logger.info("TCP server is closed. Wait for tasks to complete ...")

if __name__ == '__main__':
    asyncio.run(main())
