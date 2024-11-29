# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import asyncio
import logging
from contextlib import aclosing

from arms.beg_ft002.local_resources import LockedMachineClientInfo
from arms.beg_ft002.local_resources import get_rpi5_named_distributor
from arms.beg_ft002.local_resources import rpi5_installation_distributor
from arms.beg_ft002.local_resources import rpi5_prerequisites_distributor
from arms.beg_ft002.local_resources import ssh_key
from arms.beg_ft002.local_resources import status_endpoint
from arms.beg_ft002.mikrotik_poe_switch import poe_switch
from arms.boot_loader.raspberry import RaspberryTFTPBootloader
from arms.machines.machine import ISCSIExt4Root
from arms.machines.machine import PXEMachine
from arms.mikrotik_power_control import MikrotikPowerControl
from arms.snapshots import SnapshotContractor
from arms.snapshots import serve_contracts_loop
from arms.ssh_remote_control import SSHRemoteControl

_ip = '10.1.0.235'
_router = '10.1.0.234'
_name = 'rpi5-1'
_serial = '1d5f58bb'
_switch_port = 3


_contractor = SnapshotContractor(
    machine=PXEMachine(
        name=_name,
        power_interface=MikrotikPowerControl(poe_switch, _switch_port),
        remote_control=SSHRemoteControl(host=_ip, port=22, user="root", ssh_key=ssh_key),
        tftp_boot_loader=RaspberryTFTPBootloader(local_ip=_ip, serial=_serial),
        available_roots=[ISCSIExt4Root(_router, 3260, _name)],
        ),
    info=LockedMachineClientInfo(
        machine_name=_name,
        ip_address=_ip,
        ssh_port=22,
        username='root',
        ssh_key=ssh_key.decode(),
        ),
    )


async def main():
    async with aclosing(status_endpoint(_name)) as machine_status:
        await serve_contracts_loop(
            contractor=_contractor,
            distributors=[
                get_rpi5_named_distributor(_name),
                rpi5_prerequisites_distributor,
                rpi5_installation_distributor,
                ],
            machine_status=machine_status,
            )


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)7s %(name)s %(message).5000s")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.getLogger(__name__).info("SIGINT received. Quit")
