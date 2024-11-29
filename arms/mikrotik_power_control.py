# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
# REST documentation
# See: https://help.mikrotik.com/docs/display/ROS/REST+API
import asyncio
import logging
import time

from arms.mikrotik_switch_api import MikrotikRESTApi
from arms.power_control_interface import PowerControlInterface


class MikrotikPowerControl(PowerControlInterface):

    def __init__(self, api: MikrotikRESTApi, port: int):
        self._api = api
        self._port_name = f"ether{port}"

    async def power_on(self):
        _logger.info("%s: Enable port", self)
        await self._api.post(
            '/interface/ethernet/poe/set',
            {'.id': self._port_name, 'poe-out': 'auto-on'},
            )

    async def power_off(self):
        _logger.info("%s: Disable port", self)
        await self._api.post(
            '/interface/ethernet/poe/set',
            {'.id': self._port_name, 'poe-out': 'off'},
            )
        await self._wait_power_off()  # It takes some time for a device to lose power

    async def _wait_power_off(self):
        max_power_off_delay = 6
        timeout_at = time.monotonic() + max_power_off_delay
        while True:
            result = await self._api.get(f'/interface/{self._port_name}')
            if not _as_bool(result['running']):
                return
            if time.monotonic() > timeout_at:
                raise TimeoutError(
                    f"{self} is not down after {max_power_off_delay} sec after POE is disabled. "
                    f"The hardware connected may be using an external power supply.")
            await asyncio.sleep(0.3)

    def __repr__(self):
        return f"<Port {self._port_name}>"


def _as_bool(raw_value: str) -> bool:
    # Mikrotik sends bools as strings 'true' or 'false'
    if raw_value == 'true':
        return True
    elif raw_value == 'false':
        return False
    raise RuntimeError(f"Received unparseable bool value {raw_value!r}")


_logger = logging.getLogger(__name__)
