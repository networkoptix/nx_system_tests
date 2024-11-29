# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import asyncio
import logging
from contextlib import aclosing
from pathlib import Path

from arms.beg_ft002.local_resources import LockedMachineClientInfo
from arms.beg_ft002.local_resources import installation_market
from arms.beg_ft002.local_resources import priority_market
from arms.beg_ft002.local_resources import ssh_key
from arms.beg_ft002.local_resources import status_endpoint
from arms.beg_ft002.mikrotik_poe_switch import poe_switch
from arms.hierarchical_storage import QCOWRootDisk
from arms.machines.machine import ISCSIExt4Root
from arms.machines.machine import Machine
from arms.mikrotik_power_control import MikrotikPowerControl
from arms.snapshots import ContractsDistributor
from arms.snapshots import LocalKernelTemplate
from arms.snapshots import NamedContractTemplate
from arms.snapshots import SnapshotContractTemplate
from arms.snapshots import SnapshotContractor
from arms.snapshots import serve_contracts_loop
from arms.ssh_remote_control import SSHRemoteControl

_ip = '10.1.0.219'
_router = '10.1.0.218'
_name = 'jetson-nano-2'
_switch_port = 13


_contractor = SnapshotContractor(
    machine=Machine(
        name=_name,
        power_interface=MikrotikPowerControl(poe_switch, _switch_port),
        remote_control=SSHRemoteControl(host=_ip, port=22, user="root", ssh_key=ssh_key),
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


# ReComputer is not reliable in PXE boot, so local boot is used
_jetson_nano_boot_templates = [
    SnapshotContractTemplate(
        key=('jetsonnano', 'x64', 'ubuntu18'),
        boot_template=LocalKernelTemplate(
            QCOWRootDisk(Path('/mnt/storage/iscsi/jetsonnano/x64/ubuntu18')),
            ),
        ),
    ]
_jetson_nano_installation_distributor = ContractsDistributor(
    installation_market(), _jetson_nano_boot_templates)
_named_distributor = ContractsDistributor(
    market=priority_market(),
    # jetson-nano-2 is not allowed to run prerequisites jobs due to its unreliable nature.
    contract_templates=[NamedContractTemplate(_name, _jetson_nano_boot_templates)],
    )


async def main():
    async with aclosing(status_endpoint(_name)) as machine_status:
        await serve_contracts_loop(
            contractor=_contractor,
            distributors=[_named_distributor, _jetson_nano_installation_distributor],
            machine_status=machine_status,
            )


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)7s %(name)s %(message).5000s")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.getLogger(__name__).info("SIGINT received. Quit")
