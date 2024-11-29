# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import asyncio
import ipaddress
import logging
from contextlib import suppress
from signal import SIGINT
from signal import SIGTERM

from mediaserver_api.server import ApiServer


async def main():
    nic_ips_by_machine = {
        "rasp4-1": ipaddress.IPv4Address("10.0.8.9"),
        "rasp4-2": ipaddress.IPv4Address("10.0.8.13"),
        "jetson-nano-2g-1": ipaddress.IPv4Address("10.0.8.17"),
        "jetson-nano-2g-2": ipaddress.IPv4Address("10.0.8.21")}
    running_event_loop = asyncio.get_running_loop()
    async with ApiServer(
            api_host='127.0.0.1',
            api_port=8888,
            adapter_addresses_by_name=nic_ips_by_machine,
            ) as api_server:
        async with api_server.serve() as tcp_server:
            running_event_loop.add_signal_handler(SIGINT, tcp_server.close)
            running_event_loop.add_signal_handler(SIGTERM, tcp_server.close)
            with suppress(asyncio.CancelledError):
                await tcp_server.serve_forever()
            _logger.info("TCP server is closed. Wait for tasks to complete ...")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    _logger = logging.getLogger(__name__)
    asyncio.run(main())
