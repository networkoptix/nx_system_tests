# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import asyncio
import logging

from arms.arm_manager.server import MarketARMSession
from arms.arm_manager.server import SessionsServer
from arms.arm_manager.server import bind_server_socket
from arms.beg_ft002.local_resources import installation_market
from arms.beg_ft002.local_resources import prerequisites_market
from arms.beg_ft002.local_resources import priority_market

_logger = logging.getLogger(__name__)


async def main():
    server_socket = bind_server_socket(listen_host="0.0.0.0", listen_port=1491)
    available_markets = [priority_market(), prerequisites_market(), installation_market()]
    async with SessionsServer[MarketARMSession](server_socket) as server:
        await server.serve(lambda r, w: MarketARMSession(r, w, available_markets))


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='%(levelname)7s %(name)s %(message).5000s')
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
