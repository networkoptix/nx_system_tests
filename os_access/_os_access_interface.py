# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time
from abc import ABCMeta
from abc import abstractmethod
from contextlib import ExitStack
from contextlib import contextmanager
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from ipaddress import IPv4Address
from pathlib import Path
from subprocess import CalledProcessError
from subprocess import CompletedProcess
from subprocess import TimeoutExpired
from typing import Collection
from typing import Iterable
from typing import Literal
from typing import Mapping
from typing import NamedTuple
from typing import Optional
from typing import Sequence
from typing import Union

from ca import default_ca
from os_access import current_host_address
from os_access import get_host_by_name
from os_access._command import Run
from os_access._exceptions import ProcessStopError
from os_access._networking import Networking
from os_access._path import RemotePath
from os_access._path import copy_file
from os_access._service_interface import ServiceManager
from os_access._traffic_capture import TrafficCapture

_logger = logging.getLogger(__name__)


class Disk(NamedTuple):
    total: int
    free: int


class RamUsage(NamedTuple):
    process_usage: float
    total_usage: float
    process_usage_bytes: int
    total_usage_bytes: int
    process_usage_peak_bytes: int


class DiskIoInfo(NamedTuple):
    name: str
    reading_sec: float
    writing_sec: float
    read_bytes: int
    write_bytes: int
    read_count: int
    write_count: int


class OsAccess(ServiceManager, metaclass=ABCMeta):
    OS_FAMILY = None
    _user_description = 'NX Functional Tests user'

    def __init__(
            self,
            address, port_map,
            networking: Optional[Networking],
            ):
        self.address = address
        self._port_map = port_map
        self.networking = networking
        self.executable_suffix = ''

    @abstractmethod
    def netloc(self) -> str:
        pass

    def wait_ready(self, timeout_sec: float = 60):
        started_at = time.monotonic()
        end_at = time.monotonic() + timeout_sec
        while not self.is_ready():
            if time.monotonic() > end_at:
                raise OsAccessNotReady(
                    f"{self} is not ready after {timeout_sec} seconds. If host is Windows, guest "
                    "is Linux and guest has kernel panic on start - check "
                    "VT-x/AMD-V (must be enabled) and Microsoft Hyper-V (must be disabled). "
                    "For more info see "
                    "https://forums.virtualbox.org/viewtopic.php?f=25&t=99390")
            time.sleep(0.5)
        _logger.info("%s is ready in %.1f seconds", self, time.monotonic() - started_at)

    @abstractmethod
    def home(self, user: Optional[str] = None) -> RemotePath:
        pass

    @abstractmethod
    def tmp(self) -> RemotePath:
        pass

    @abstractmethod
    def path(self, *parts: str) -> RemotePath:
        pass

    @property
    @abstractmethod
    def traffic_capture(self) -> TrafficCapture:
        pass

    @abstractmethod
    def Popen(self, command: Union[str, Sequence[str]]) -> Run:  # noqa PyPep8Naming
        pass

    @abstractmethod
    def run(
            self,
            command: Union[str, Sequence[str]],
            input: Optional[bytes] = None,
            timeout_sec: float = 60,
            check: bool = True,
            ) -> CompletedProcess:
        pass

    def diagnostic_report(self, artifacts_dir: Path):
        report = self._get_diagnostic_report()
        self._write_diagnostic_report_file(artifacts_dir, report)

    def _write_diagnostic_report_file(self, artifacts_dir: Path, report: bytes):
        prefix = self.netloc().replace(':', '-')
        diagnostic_report_file = artifacts_dir / f'{prefix}_diagnostic_report.txt'
        timestamp = datetime.now().astimezone()
        header = f"DIAGNOSTIC REPORT AT: {timestamp.isoformat(' ', 'seconds')}\n\n".encode()
        diagnostic_report_file.write_bytes(header + report)

    def _handle_command_with_timeout(self, command: str, timeout_sec: float) -> bytes:
        max_attempts = 3
        output = b''
        for _ in range(max_attempts):
            try:
                output = self.run(command, timeout_sec=timeout_sec, check=False).stdout
            except TimeoutExpired:
                _logger.warning("Couldn't get command output in time:\n%s", command)
            else:
                break
        else:
            _logger.error(
                "Command was not executed after %d attempts:\n%s", max_attempts, command)
        return output

    @contextmanager
    def traffic_capture_collector(self, artifacts_dir: Path):
        self.traffic_capture.stop()
        for old_capture_file in self.traffic_capture.files():
            old_capture_file.unlink()
        self.traffic_capture.start()
        try:
            yield
        finally:
            try:
                self.traffic_capture.stop()
            except ProcessStopError:
                _logger.warning(
                    "Traffic capture is still running. "
                    "Capture files would be damaged if collected now. "
                    "Skip collection.")
            else:
                prefix = self.netloc().replace(':', '-')
                for cap_file in self.traffic_capture.files():
                    copy_file(cap_file, artifacts_dir / f'{prefix}_{cap_file.name}')

    @contextmanager
    def prepared_one_shot_vm(self, artifacts_dir: Path):
        with ExitStack() as exit_stack:
            self._clear_and_enable_logs()
            exit_stack.callback(self.download_system_logs, artifacts_dir)
            exit_stack.callback(self.diagnostic_report, artifacts_dir)
            self.networking.allow_subnet('192.168.254.0/24')
            self.networking.allow_hosts([
                'artifactory.us.nxteam.dev',
                current_host_address(),  # For using additional services on the host machine.
                ])
            self.networking.disable_internet()
            self.set_datetime(datetime.now(timezone.utc))
            self.add_trusted_certificate(_lets_encrypt_stage_cert)
            self.add_trusted_certificate(_amazon_root_cert)
            self.add_trusted_certificate(default_ca().cert_path)
            ca_path = Path(__file__).parent.parent / 'vm/virtual_box/configuration'
            self.add_trusted_certificate(ca_path / 'Starfield Class 2 Certification Authority.cer')
            self.add_trusted_certificate(ca_path / 'ISRG Root X1.cer')  # For Let's Encrypt certificates.
            yield

    @abstractmethod
    def close(self):
        pass

    @abstractmethod
    def get_datetime(self) -> datetime:
        pass

    @abstractmethod
    def set_datetime(self, new_time: datetime) -> None:
        pass

    def shift_time(self, delta: timedelta) -> None:
        self.set_datetime(self.get_datetime() + delta)

    @abstractmethod
    def _clear_and_enable_logs(self):
        pass

    @abstractmethod
    def download_system_logs(self, target_local_dir: Path):
        pass

    @abstractmethod
    def is_ready(self) -> bool:
        pass

    @abstractmethod
    def reboot(self):
        """Reboot and return when OS has been rebooted."""
        pass

    @abstractmethod
    def kill_all_by_name(self, executable_name: str):
        pass

    @abstractmethod
    def fs_root(self) -> RemotePath:
        pass

    def _disk_space_holder(self) -> RemotePath:
        return self.fs_root() / 'space_holder.tmp'

    @abstractmethod
    def volumes(self) -> Mapping[RemotePath, Disk]:
        pass

    def system_disk(self):
        return self.volumes()[self.fs_root()]

    def _hold_disk_space(self, to_consume_bytes: int):
        self.create_file(self._disk_space_holder(), to_consume_bytes)

    @abstractmethod
    def create_file(self, file_path: RemotePath, file_size_b: int):
        pass

    def clean_up_disk_space(self):
        try:
            self._disk_space_holder().unlink()
        except FileNotFoundError:
            pass

    def _get_holder_size(self) -> int:
        try:
            return self._disk_space_holder().size()
        except FileNotFoundError:
            return 0

    def maintain_free_disk_space(self, should_leave_bytes: int):
        """Limit free disk space like in real life.

        One-time allocation (reservation) of disk space is not enough. OS or other software
        (Mediaserver) may free disk space by deletion of temporary files or archiving other files,
        especially as reaction on low free disk space, limiting of which is the point of this
        function. That's why disk space is checked several times and a holder file is adjusted
        when necessary. Sometimes the reported free space might be greater than the real one.
        In that case the holder file size is decreased by little in hope to avoid the allocation
        problem at the next loop tick.

        Note that it could lead to the loss of logs and may cause a malfunction of OS or software.

        Execution may take long!
        """
        interval_sec = 0.5
        maintained_sec = 0
        holder_size = self._get_holder_size()
        target_free_min = 5 * 1024 * 1024
        target_free_max = should_leave_bytes + 5 * 1024 * 1024
        if should_leave_bytes < target_free_min:
            raise RuntimeError(
                f"The 'should_leave_bytes' MUST be more than or equal to {target_free_min}")
        target_free = should_leave_bytes
        delta_fraction = 1.0
        while maintained_sec < 30:
            free_now = self.system_disk().free
            if not target_free_min <= free_now <= target_free_max:
                delta = free_now - target_free
                new_holder_size = holder_size + int(delta * delta_fraction)
                if delta < 0:
                    _logger.info(
                        "Decrease the holder file size %s => %s", holder_size, new_holder_size)
                else:
                    _logger.info(
                        "Increase the holder file size %s => %s", holder_size, new_holder_size)
                try:
                    self._hold_disk_space(new_holder_size)
                except CalledProcessError as err:
                    if b'There is not enough space on the disk' not in err.stderr:
                        raise
                    delta_fraction -= 0.1
                    if delta_fraction < 0:
                        raise RuntimeError(
                            "delta_fraction is negative. "
                            "All attempts to create the holder file have failed")
                    _logger.warning(
                        "Error at disk allocation. Decrease delta ratio down to %s", delta_fraction)
                    continue
                else:
                    holder_size = new_holder_size
                    maintained_sec = 0
                    delta_fraction = 1.0
            else:
                maintained_sec += interval_sec
            _logger.debug("Wait to allow OS and software to clean up: %.1f sec", interval_sec)
            time.sleep(interval_sec)

    @abstractmethod
    def file_md5(self, file_path: RemotePath):
        pass

    @abstractmethod
    def folder_contents_size(self, folder: RemotePath):
        pass

    @abstractmethod
    def files_size_sum(self, folder: RemotePath, extension: str) -> int:
        pass

    @abstractmethod
    def source_address(self) -> str:
        pass

    @contextmanager
    @abstractmethod
    def mount_disabled(self, mount_point: Path):
        pass

    @abstractmethod
    def dismount_fake_disk(self, mount_point: RemotePath):
        pass

    @abstractmethod
    def mount_fake_disk(self, letter: str, size_bytes: int) -> RemotePath:
        pass

    @abstractmethod
    def is_fake_disk_mounted(self, letter: str):
        pass

    @abstractmethod
    def mount_smb_share(
            self,
            mount_point: str,
            path: str,
            username: str,
            password: str,
            ):
        pass

    @abstractmethod
    def dismount_smb_share(self, mount_point: str, lazy: bool = True):
        pass

    @abstractmethod
    def list_mounted_disks(self) -> Mapping[RemotePath, str]:
        pass

    @abstractmethod
    def _list_disks_without_partition(self) -> Collection[str]:
        pass

    def _wait_for_newly_attached_disk_appears(self) -> str:
        timeout_sec = 40
        started_at = time.monotonic()
        while True:
            _logger.debug(
                "Checking newly attached disk, time passed %.1f/%.1f",
                time.monotonic() - started_at, timeout_sec)
            disks_without_partition = self._list_disks_without_partition()
            if len(disks_without_partition) == 1:
                [disk_without_partition] = disks_without_partition
                return disk_without_partition
            if len(disks_without_partition) > 1:
                raise RuntimeError(
                    f"Found {len(disks_without_partition)} newly attached disks, "
                    "unable to choose which one to mount")
            if time.monotonic() - started_at > timeout_sec:
                raise RuntimeError(f"Newly attached disk not found after {timeout_sec} seconds")
            time.sleep(0.5)

    @abstractmethod
    def mount_disk(self, letter: str) -> RemotePath:
        pass

    @abstractmethod
    def _hosts_file(self) -> RemotePath:
        pass

    def set_hosts(self, ip_to_aliases: Mapping[str, Iterable[str]], append: bool = False):
        mark = '# Functional Tests'
        path = self._hosts_file()
        contents_old = path.read_text('ascii')
        lines_old = contents_old.splitlines()
        if append:
            lines_new = lines_old[:]
        else:
            lines_new = []
            for line in lines_old:
                if not line.endswith(mark):
                    lines_new.append(line)
        for ip, aliases in ip_to_aliases.items():
            _logger.debug("Set host '%s' aliases: %r", ip, aliases)
            if not aliases:
                raise ValueError("No aliases for {}".format(ip))
            lines_new.append(' '.join([ip, *aliases, mark]))
        contents_new = '\n'.join(lines_new) + '\n'
        path.write_text(contents_new, 'ascii')

    def cache_dns_in_etc_hosts(self, hostnames: Sequence[str]):
        """Minimize reliance on DNS; avoid adding another firewall rule.

        All existing rules are rewritten. Call once per test or provide with
        all hostnames that should be cached.
        """
        self.set_hosts({get_host_by_name(h): [h] for h in hostnames})

    @abstractmethod
    def unzip(self, archive_path: RemotePath, dest_dir: RemotePath):
        pass

    @abstractmethod
    def arch(self) -> str:
        pass

    @abstractmethod
    def create_user(self, user: str, password: str, exist_ok: bool = False):
        pass

    @abstractmethod
    def disable_user(self, name: str):
        pass

    @abstractmethod
    def create_smb_share(self, name: str, path: RemotePath, user: str):
        pass

    @abstractmethod
    def create_iscsi_target(self, size: int, alias: str) -> str:
        pass

    @abstractmethod
    def mount_iscsi_disk(self, address: IPv4Address, target_name: str) -> RemotePath:
        pass

    @abstractmethod
    def dismount_iscsi_disk(self, target_iqn: str):
        pass

    @abstractmethod
    def allow_access(self, path: RemotePath, user: str):
        pass

    @abstractmethod
    def allow_access_for_everyone(self, path: RemotePath):
        pass

    @abstractmethod
    def _get_diagnostic_report(self) -> bytes:
        pass

    @abstractmethod
    def get_cpu_name(self) -> str:
        pass

    @abstractmethod
    def get_process_thread_count(self, pid: int) -> int:
        pass

    @abstractmethod
    def get_ram_usage(self, pid: int) -> RamUsage:
        pass

    @abstractmethod
    def _get_used_memory_mbytes(self) -> int:
        pass

    @abstractmethod
    def _start_ram_load(self, ram_mbytes: int):
        pass

    def start_ram_load(self, ram_mbytes: int = 500):
        used_before = self._get_used_memory_mbytes()
        self._start_ram_load(ram_mbytes)
        timeout_sec = 30
        started = time.monotonic()
        tolerance = 0.05
        while time.monotonic() - started < timeout_sec:
            if self._get_used_memory_mbytes() - used_before > (1 - tolerance) * ram_mbytes:
                break
            time.sleep(1)
        else:
            raise RuntimeError(f"Failed to allocate {ram_mbytes} MB of RAM")

    @abstractmethod
    def stop_ram_load(self):
        pass

    @staticmethod
    def _get_port(
            port_map: Mapping[Literal['tcp', 'udp'], Mapping[int, int]],
            proto: Literal['tcp', 'udp'],
            port: int) -> int:
        return port if port_map is None else port_map[proto][port]

    def get_port(self, proto: Literal['tcp', 'udp'], port: int) -> int:
        return self._get_port(self._port_map, proto, port)

    @abstractmethod
    def list_total_cpu_usage(self, sample_interval_sec: int, sample_count: int) -> Sequence[float]:
        pass

    @abstractmethod
    def list_process_cpu_usage(
            self,
            pid: int,
            sample_interval_sec: int,
            sample_count: int,
            ) -> Sequence[float]:
        pass

    def run_cpu_load(self, cpu_load_duration_sec: int):
        try:
            self._start_cpu_load()
            time.sleep(cpu_load_duration_sec)
        finally:
            self._stop_cpu_load()

    @abstractmethod
    def _start_cpu_load(self):
        pass

    @abstractmethod
    def _stop_cpu_load(self):
        pass

    @abstractmethod
    def compact(self):
        pass

    @abstractmethod
    def add_trusted_certificate(self, cert_path: Path):
        pass

    @abstractmethod
    def get_cpu_usage(self) -> float:
        pass

    @abstractmethod
    def get_cpu_time_process(self, pid: int) -> float:
        pass

    @abstractmethod
    def get_io_time(self) -> Collection[DiskIoInfo]:
        pass

    @abstractmethod
    def get_open_files_count(self, pid: int) -> int:
        pass

    @abstractmethod
    def get_pid_by_name(self, executable_name: str) -> int:
        pass


class OsAccessNotReady(Exception):
    pass


_lets_encrypt_stage_cert = Path(__file__).parent / 'letsencrypt-stg.pem'
assert _lets_encrypt_stage_cert.exists()
_amazon_root_cert = Path(__file__).parent / 'amazon-root.pem'
assert _amazon_root_cert.exists()
