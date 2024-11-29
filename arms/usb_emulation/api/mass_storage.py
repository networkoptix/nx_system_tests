# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import asyncio
import ipaddress
from contextlib import suppress
from signal import SIGINT
from signal import SIGTERM

from usb_emulation.api.async_queue import SharedQueue
from usb_emulation.usb.usb_registry import UsbDeviceRegistry
from usb_emulation.usb_ip.async_usbip_server import UsbIpSessionsManager
from usb_emulation.usb_ip.async_usbip_server import UsbIpStreamServer


class _UsbIpMassStorageServer:

    def __init__(self, ip_address: ipaddress.IPv4Address, queue: SharedQueue):
        self._registry = UsbDeviceRegistry(str(ip_address))
        self._queue = queue
        self._server = UsbIpStreamServer(str(ip_address))
        self._manager = UsbIpSessionsManager(self._registry)
        self._tcp_server = None
        self._serve_context = None

    async def __aenter__(self):
        await self._manager.__aenter__()
        self._waiter_coroutine = asyncio.get_running_loop().create_task(self.wait_for_attach_device())
        self._serve_context = self._server.serve(self._manager.schedule_session)
        self._tcp_server = await self._serve_context.__aenter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._serve_context.__aexit__(exc_type, exc_val, exc_tb)
        await self._manager.__aexit__(exc_type, exc_val, exc_tb)
        if not self._waiter_coroutine.done():
            self._waiter_coroutine.cancel()
        with suppress(asyncio.CancelledError):
            await self._waiter_coroutine

    async def wait_for_attach_device(self):
        while True:
            size_mb = await self._queue.async_get()
            self._registry.create_mass_storage(size_mb)

    async def run(self):
        running_event_loop = asyncio.get_running_loop()
        running_event_loop.add_signal_handler(SIGINT, self._tcp_server.close)
        running_event_loop.add_signal_handler(SIGTERM, self._tcp_server.close)
        with suppress(asyncio.CancelledError):
            await self._tcp_server.serve_forever()


async def _main(ip_address: ipaddress.IPv4Address, queue: SharedQueue):
    storage_server = _UsbIpMassStorageServer(ip_address, queue)
    async with storage_server:
        await storage_server.run()


def run_mass_storage(ip_address: ipaddress.IPv4Address, queue: SharedQueue):
    try:
        asyncio.run(_main(ip_address, queue))
    except BaseException:
        with open('traceback.txt', 'w') as f:
            import traceback
            f.write(traceback.format_exc())
