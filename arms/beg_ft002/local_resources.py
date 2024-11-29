# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from functools import lru_cache
from pathlib import Path
from typing import TypedDict

from arms.hierarchical_storage import QCOWRootDisk
from arms.machine_status import StatusEndpoint
from arms.machine_status import UnixSocketStatusEndpoint
from arms.market import Market
from arms.market import SingleDirectoryStorage
from arms.market import UnixSocketMarket
from arms.ptftp_control import LocalTFTPControl
from arms.snapshots import ContractsDistributor
from arms.snapshots import ISCSIBootTemplate
from arms.snapshots import NamedContractTemplate
from arms.snapshots import SnapshotContractTemplate
from arms.tftp_roots_storage import LocalTFTPRoot


@lru_cache
def installation_market() -> Market:
    local_path = Path('/tmp/arms_market')
    # Every file in the dir is intended to be created\removed by any user
    local_path.mkdir(mode=0o777, exist_ok=True)
    return UnixSocketMarket(SingleDirectoryStorage(local_path), priority=0)


@lru_cache
def priority_market() -> Market:
    local_path = Path('/tmp/arms_market_by_name')
    # Every file in the dir is intended to be created\removed by any user
    local_path.mkdir(mode=0o777, exist_ok=True)
    return UnixSocketMarket(SingleDirectoryStorage(local_path), priority=0)


@lru_cache
def prerequisites_market() -> Market:
    local_path = Path('/tmp/arms_prerequisites_market')
    # Every file in the dir is intended to be created\removed by any user
    local_path.mkdir(mode=0o777, exist_ok=True)
    return UnixSocketMarket(SingleDirectoryStorage(local_path), priority=0)


def get_rpi4_named_distributor(name: str) -> ContractsDistributor:
    return ContractsDistributor(
        market=priority_market(),
        contract_templates=[NamedContractTemplate(name, _rpi4_snapshot_templates)],
        )


def get_rpi5_named_distributor(name: str) -> ContractsDistributor:
    return ContractsDistributor(
        market=priority_market(),
        contract_templates=[NamedContractTemplate(name, _rpi5_snapshot_templates)],
        )


def get_jetson_nano_named_distributor(name: str) -> ContractsDistributor:
    return ContractsDistributor(
        market=priority_market(),
        contract_templates=[NamedContractTemplate(name, _jetson_nano_snapshot_templates)],
        )


def get_orin_nano_named_distributor(name: str) -> ContractsDistributor:
    return ContractsDistributor(
        market=priority_market(),
        contract_templates=[NamedContractTemplate(name, _orin_nano_snapshot_templates)],
        )


def status_endpoint(name: str) -> StatusEndpoint:
    local_path = Path('/tmp/status')
    local_path.mkdir(mode=0o777, exist_ok=True)
    socket_path = local_path / f'{name}.sock'
    socket_path.unlink(missing_ok=True)
    return UnixSocketStatusEndpoint(socket_path)


ssh_key = Path(__file__).parent.parent.parent.joinpath('_internal/arm.rsa.key').read_bytes()


class LockedMachineClientInfo(TypedDict):
    machine_name: str
    ip_address: str
    ssh_port: int
    username: str
    ssh_key: str


_tftp_server = LocalTFTPControl(Path('/tmp/ptftp_control'))


_rpi4_snapshot_templates = [
    SnapshotContractTemplate(
        key=('raspberry4', 'x32', 'raspbian10'),
        boot_template=ISCSIBootTemplate(
            QCOWRootDisk(Path('/mnt/storage/iscsi/raspberry4/x32/raspbian10')),
            LocalTFTPRoot(_tftp_server, Path('/mnt/storage/tftp/raspberry4/x32/raspbian10')),
            ),
        ),
    SnapshotContractTemplate(
        key=('raspberry4', 'x32', 'raspbian11'),
        boot_template=ISCSIBootTemplate(
            QCOWRootDisk(Path('/mnt/storage/iscsi/raspberry4/x32/raspbian11')),
            LocalTFTPRoot(_tftp_server, Path('/mnt/storage/tftp/raspberry4/x32/raspbian11')),
            ),
        ),
    SnapshotContractTemplate(
        key=('raspberry4', 'x32', 'raspbian12'),
        boot_template=ISCSIBootTemplate(
            QCOWRootDisk(Path('/mnt/storage/iscsi/raspberry4/x32/raspbian12')),
            LocalTFTPRoot(_tftp_server, Path('/mnt/storage/tftp/raspberry4/x32/raspbian12')),
            ),
        ),
    SnapshotContractTemplate(
        key=('raspberry4', 'x64', 'raspbian11'),
        boot_template=ISCSIBootTemplate(
            QCOWRootDisk(Path('/mnt/storage/iscsi/raspberry4/x64/raspbian11')),
            LocalTFTPRoot(_tftp_server, Path('/mnt/storage/tftp/raspberry4/x64/raspbian11')),
            ),
        ),
    SnapshotContractTemplate(
        key=('raspberry4', 'x64', 'raspbian12'),
        boot_template=ISCSIBootTemplate(
            QCOWRootDisk(Path('/mnt/storage/iscsi/raspberry4/x64/raspbian12')),
            LocalTFTPRoot(_tftp_server, Path('/mnt/storage/tftp/raspberry4/x64/raspbian12')),
            ),
        ),
    ]


_rpi5_snapshot_templates = [
    SnapshotContractTemplate(
        key=('raspberry5', 'x32', 'raspbian12'),
        boot_template=ISCSIBootTemplate(
            QCOWRootDisk(Path('/mnt/storage/iscsi/raspberry5/x32/raspbian12')),
            LocalTFTPRoot(_tftp_server, Path('/mnt/storage/tftp/raspberry5/x32/raspbian12')),
            ),
        ),
    SnapshotContractTemplate(
        key=('raspberry5', 'x64', 'raspbian12'),
        boot_template=ISCSIBootTemplate(
            QCOWRootDisk(Path('/mnt/storage/iscsi/raspberry5/x64/raspbian12')),
            LocalTFTPRoot(_tftp_server, Path('/mnt/storage/tftp/raspberry5/x64/raspbian12')),
            ),
        ),
    ]


_jetson_nano_snapshot_templates = [
    SnapshotContractTemplate(
        key=('jetsonnano', 'x64', 'ubuntu18'),
        boot_template=ISCSIBootTemplate(
            QCOWRootDisk(Path('/mnt/storage/iscsi/jetsonnano/x64/ubuntu18')),
            LocalTFTPRoot(_tftp_server, Path('/mnt/storage/tftp/jetsonnano/x64/ubuntu18')),
            ),
        ),
    ]


_orin_nano_snapshot_templates = [
    SnapshotContractTemplate(
        key=('orin_nano', 'x64', 'ubuntu22'),
        boot_template=ISCSIBootTemplate(
            QCOWRootDisk(Path('/mnt/storage/iscsi/orin_nano/x64/ubuntu22')),
            LocalTFTPRoot(_tftp_server, Path('/mnt/storage/tftp/orin_nano/x64/ubuntu22')),
            ),
        ),
    ]

jetson_nano_installation_distributor = ContractsDistributor(
    installation_market(), _jetson_nano_snapshot_templates)
jetson_nano_prerequisites_distributor = ContractsDistributor(
    prerequisites_market(), _jetson_nano_snapshot_templates)
rpi4_installation_distributor = ContractsDistributor(installation_market(), _rpi4_snapshot_templates)
rpi4_prerequisites_distributor = ContractsDistributor(
    prerequisites_market(), _rpi4_snapshot_templates)
rpi5_installation_distributor = ContractsDistributor(installation_market(), _rpi5_snapshot_templates)
rpi5_prerequisites_distributor = ContractsDistributor(
    prerequisites_market(), _rpi5_snapshot_templates)
orin_nano_installation_distributor = ContractsDistributor(
    installation_market(), _orin_nano_snapshot_templates)
orin_nano_prerequisites_distributor = ContractsDistributor(
    prerequisites_market(), _orin_nano_snapshot_templates)
