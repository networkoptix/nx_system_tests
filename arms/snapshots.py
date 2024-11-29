# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import asyncio
import logging
import random
import time
from abc import ABCMeta
from abc import abstractmethod
from collections.abc import Collection
from collections.abc import Mapping
from collections.abc import Sequence
from contextlib import AbstractAsyncContextManager
from contextlib import asynccontextmanager
from contextlib import contextmanager
from typing import Any

from arms.hierarchical_storage import ChildExists
from arms.hierarchical_storage import PendingSnapshot
from arms.hierarchical_storage import RootDisk
from arms.hierarchical_storage import SnapshotAlreadyPending
from arms.hierarchical_storage.storage import ParentNotExist
from arms.machine_status import StatusEndpoint
from arms.machines.machine import ISCSIExt4Root
from arms.machines.machine import Machine
from arms.machines.machine import PXEMachine
from arms.machines.machine import RunningMachine
from arms.market import AcceptedContract
from arms.market import Contract
from arms.market import Market
from arms.tftp_roots_storage import TFTPRoot


class ContractTemplate(metaclass=ABCMeta):

    @abstractmethod
    async def accept(self, contract_description: Mapping[str, Any]) -> 'Snapshot':
        pass


class SnapshotContractTemplate(ContractTemplate):

    def __init__(self, key: Sequence[str], boot_template: 'BootTemplate'):
        self._key = key
        self._boot_template = boot_template

    async def accept(self, contract_description: Mapping[str, Any]) -> 'Snapshot':
        contract_boot_key = (
            contract_description['model'],
            contract_description['arch'],
            contract_description['os'],
            )
        if contract_boot_key != self._key:
            raise _UnsuitableContract(f"{self}: Ignore contract key {contract_boot_key}")
        disk_stems = contract_description['disk_stems']
        boot_configuration = self._get_boot_configuration(disk_stems)
        return Snapshot(boot_configuration, disk_stems)

    def _get_boot_configuration(self, disk_stems: Sequence[str]) -> 'BootConfiguration':
        try:
            return self._boot_template.get_boot_configuration(*disk_stems)
        except SnapshotAlreadyPending:
            raise _ImpossibleContract(
                f"{self}: Snapshot for {disk_stems} is already being created")
        except ParentNotExist:
            raise _ImpossibleContract(f"{self}: Can't find snapshot for {disk_stems}")
        except ChildExists:
            raise _ImpossibleContract(f"{self}: Snapshot for {disk_stems} already exists")

    def __repr__(self):
        return f'<{self.__class__.__name__}: {self._key}>'


class NamedContractTemplate(ContractTemplate):

    def __init__(self, contract_name: str, available_contract_templates: Collection['ContractTemplate']):
        self._contract_name = contract_name
        self._available_contract_templates = available_contract_templates

    async def accept(self, contract_description: Mapping[str, Any]) -> 'Snapshot':
        contract_name = contract_description.get('name')
        if contract_name != self._contract_name:
            raise _UnsuitableContract(f"{self}: Ignore contract name {contract_name!r}")
        for contract_template in self._available_contract_templates:
            try:
                return await contract_template.accept(contract_description)
            except _UnsuitableContract:
                _logger.debug(
                    "%s: %s can't serve %s", self, contract_template, contract_description)
        disk_stems = (
            contract_description['model'],
            contract_description['arch'],
            contract_description['os'],
            )
        raise _ImpossibleContract(f"{self}: Can't find snapshot for {disk_stems}")

    def __repr__(self):
        return f'<{self.__class__.__name__}: {self._contract_name}>'


class _UnsuitableContract(Exception):
    pass


class _ImpossibleContract(Exception):
    pass


class _NoContractsAvailable(Exception):
    pass


class BootConfiguration(metaclass=ABCMeta):

    @abstractmethod
    async def boot_clean(self, machine: Machine) -> RunningMachine:
        pass


class BootTemplate(metaclass=ABCMeta):

    @abstractmethod
    def get_boot_configuration(self, *disk_stems: str) -> BootConfiguration:
        pass


class ISCSIBootTemplate(BootTemplate):

    def __init__(self, root_disk: RootDisk, tftp_root: TFTPRoot):
        self._root_disk = root_disk
        self._tftp_root = tftp_root

    def get_boot_configuration(self, *disk_stems: str):
        self._root_disk.prune()
        parent = self._root_disk
        for stem in disk_stems[:-1]:
            parent = parent.get_diff(stem)
        pending_snapshot_disk = PendingSnapshot(parent, disk_stems[-1])
        return ISCSITFTPBootConfiguration(self._tftp_root, pending_snapshot_disk)


class LocalKernelTemplate(BootTemplate):

    def __init__(self, root_disk: RootDisk):
        self._root_disk = root_disk

    def get_boot_configuration(self, *disk_stems: str):
        self._root_disk.prune()
        parent = self._root_disk
        for stem in disk_stems[:-1]:
            parent = parent.get_diff(stem)
        pending_snapshot_disk = PendingSnapshot(parent, disk_stems[-1])
        return ISCSILocalKernelBootConfiguration(pending_snapshot_disk)


class Snapshot:

    def __init__(self, boot_configuration: BootConfiguration, disk_stems: Sequence[str]):
        self._disk_stems = disk_stems
        self._boot_configuration = boot_configuration

    async def boot(self, machine: Machine) -> '_RunningSnapshot':
        running_machine = await self._boot_configuration.boot_clean(machine)
        return _RunningSnapshot(running_machine)

    def __repr__(self):
        return f'<Snapshot: {self._disk_stems}>'


class _RunningSnapshot:

    def __init__(self, running_machine: RunningMachine):
        self._running_machine = running_machine
        self._rollback = True

    async def serve(self, accepted_contract: AcceptedContract):
        async for command, description in accepted_contract.handle():
            if description['snapshot'] == 'commit':
                try:
                    await self._commit()
                except Exception as err:
                    await command.report_failure({"exception": str(err)})
                    raise
                await command.report_success({})
            else:
                _logger.warning("%s: Ignore command %s", self._running_machine, description)
        _logger.info("%s: Contract is successfully fulfilled", self._running_machine)

    async def _commit(self):
        await self._running_machine.commit()
        self._rollback = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._rollback:
            await self._running_machine.rollback()


class ISCSILocalKernelBootConfiguration(BootConfiguration):

    def __init__(self, machine_disk: PendingSnapshot):
        self._machine_disk = machine_disk

    async def boot_clean(self, machine: Machine) -> RunningMachine:
        await machine.power_off()
        root_fs = machine.get_root_fs(ISCSIExt4Root)
        await root_fs.detach_disk()
        await root_fs.attach_disk(self._machine_disk.get_filesystem_path())
        await machine.start()
        return RunningMachine(machine, self._machine_disk, root_fs)


class ISCSITFTPBootConfiguration(BootConfiguration):

    def __init__(self, tftp_root: TFTPRoot, machine_disk: PendingSnapshot):
        self._tftp_root = tftp_root
        self._machine_disk = machine_disk

    async def boot_clean(self, pxe_machine: PXEMachine) -> RunningMachine:
        await pxe_machine.power_off()
        root_fs = pxe_machine.get_root_fs(ISCSIExt4Root)
        await root_fs.detach_disk()
        await root_fs.attach_disk(self._machine_disk.get_filesystem_path())
        pxe_machine.config_tftp(self._tftp_root, root_fs.get_arguments())
        await pxe_machine.start()
        return RunningMachine(pxe_machine, self._machine_disk, root_fs)


class SnapshotContractor:

    def __init__(self, machine: Machine, info: Mapping[str, Any]):
        self._machine = machine
        self._info = info

    async def serve_single_contract(self, contract: Contract, snapshot: Snapshot):
        _logger.info("%s: Serve %s for %s", self, contract, snapshot)
        async with self._running(snapshot) as running_snapshot:  # type: _RunningSnapshot
            async with self._accepted(contract) as accepted_contract:  # type: AcceptedContract
                await running_snapshot.serve(accepted_contract)

    @asynccontextmanager
    async def _running(self, snapshot: Snapshot) -> AbstractAsyncContextManager[_RunningSnapshot]:
        running_snapshot_machine = await snapshot.boot(self._machine)
        async with running_snapshot_machine:
            yield running_snapshot_machine

    @asynccontextmanager
    async def _accepted(
            self, contract: Contract) -> AbstractAsyncContextManager['AcceptedContract']:
        with self._time_spent(contract):
            async with contract.accepted(self._info) as accepted_contract:
                yield accepted_contract

    @contextmanager
    def _time_spent(self, contract: Contract):
        _logger.info("%s: Start serving %s", self, contract)
        start_time = time.monotonic()
        try:
            yield
        except Exception:
            elapsed = time.monotonic() - start_time
            _logger.exception("%s: %s NOT fulfilled. Elapsed %.03f", self, contract, elapsed)
            raise
        elapsed = time.monotonic() - start_time
        _logger.info("%s: %s fulfilled. Elapsed %.03f", self, contract, elapsed)

    def __repr__(self):
        return f'<Contractor: {self._machine}>'


class ContractsDistributor:

    def __init__(self, market: Market, contract_templates: Collection[ContractTemplate]):
        self._market = market
        self._contract_templates = contract_templates

    async def pick_first_feasible_contract(self) -> tuple[Contract, Snapshot]:
        async for contract, description in self._market.iter_pending_contracts():
            for boot_template in self._contract_templates:
                try:
                    snapshot = await boot_template.accept(description)
                except _UnsuitableContract as err:
                    _logger.debug("%s ignored %s: [%s]", boot_template, description, err)
                    continue
                except _ImpossibleContract as err:
                    _logger.exception("%s rejected %s:", boot_template, description)
                    await contract.reject(str(err))
                    break
                except Exception:
                    _logger.exception("%s ignored %s:", boot_template, description)
                    contract.ignore()
                    break
                return contract, snapshot
            else:
                _logger.debug("Couldn't find suitable boot template for %s", description)
                contract.ignore()
        raise _NoContractsAvailable()


async def serve_contracts_loop(
        contractor: SnapshotContractor,
        distributors: Sequence[ContractsDistributor],
        machine_status: StatusEndpoint,
        ):
    _logger.info("%s: Start looking for a contract", contractor)
    while True:
        mandatory_delay = random.randint(1, 10)
        _logger.info("%s: Wait %s before contract search...", contractor, mandatory_delay)
        await asyncio.sleep(mandatory_delay)
        for distributor in distributors:
            try:
                contract, snapshot = await distributor.pick_first_feasible_contract()
            except _NoContractsAvailable:
                _logger.info("%s: No contracts found", contractor)
                continue
            with machine_status.serving():
                await contractor.serve_single_contract(contract, snapshot)
            break


_logger = logging.getLogger(__name__)
