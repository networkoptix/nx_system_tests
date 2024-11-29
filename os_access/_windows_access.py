# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import errno
import functools
import logging
import math
import re
import string
import time
from contextlib import closing
from contextlib import contextmanager
from contextlib import suppress
from datetime import datetime
from http.client import HTTPConnection
from pathlib import Path
from subprocess import CalledProcessError
from typing import Collection
from typing import Mapping
from typing import Optional

from os_access._os_access_interface import Disk
from os_access._os_access_interface import DiskIoInfo
from os_access._os_access_interface import OsAccess
from os_access._os_access_interface import RamUsage
from os_access._path import copy_file
from os_access._powershell import extract_script_from_command_line
from os_access._powershell import run_powershell_script
from os_access._powershell import start_powershell_script
from os_access._smb_path import SmbPath
from os_access._smb_path import _SmbConnectionPool
from os_access._windows_networking import WindowsNetworking
from os_access._windows_performance_counters import PerformanceCounterEngine
from os_access._windows_registry import WindowsRegistry
from os_access._windows_service import _WindowsService
from os_access._windows_traffic_capture import WindowsTrafficCapture
from os_access._windows_users import UserAccount
from os_access._windows_users import UserProfile
from os_access._winrm import WinRM
from os_access._winrm import WinRMOperationTimeoutError
from os_access._winrm import WinRmUnauthorized
from os_access._winrm import WmiFault
from os_access._winrm import WmiInvokeFailed
from os_access._winrm import resolve_resource_uri
from os_access._winrm_shell import WinRMShell

_logger = logging.getLogger(__name__)


class WindowsAccess(OsAccess):
    """High-level access to a remote Windows.

    Access WMI and run CMD commands via WinRM.
    Access filesystem via SMB.
    Run PowerShell commands over CMD.
    """

    OS_FAMILY = "windows"
    WINRM_PORT = 5985
    _cpu_load_script = '$result = 1; foreach ($number in 1..2147483647) {$result *= $number};'
    _ns = 1 / 1000 / 1000 / 1000
    _tick = 100 * _ns

    def __init__(self, address, username, password, port_map=None):
        port = self._get_port(port_map, 'tcp', self.WINRM_PORT)
        self.winrm = WinRM(address, port, username, password)
        self.registry = WindowsRegistry(self.winrm)
        super(WindowsAccess, self).__init__(
            address, port_map,
            WindowsNetworking(self.winrm),
            )
        self.username = username
        self.password = password
        self.executable_suffix = '.exe'
        self._smb_connection_pool = _SmbConnectionPool(
            username,
            password,
            address,
            self.get_port('tcp', 445),
            )
        self._performance_counter_engine = PerformanceCounterEngine(self.winrm)
        self._winrm_shell: Optional[WinRMShell] = None
        self._traffic_capture: Optional[WindowsTrafficCapture] = None

    def __repr__(self):
        return f'<{self.__class__.__name__} {self.netloc()}>'

    def netloc(self):
        """Prefer WinRM; SMB is "secondary"."""
        return self.winrm.netloc()

    def _winrm_is_working(self):
        port = self.get_port('tcp', self.WINRM_PORT)
        try:
            # There is a brief period immediately after starting the Windows boot process during
            # which a request to WinRM will hang for about 90 seconds. To avoid this, try making an
            # HTTP request with a short timeout.
            with closing(HTTPConnection(self.address, port, timeout=1)) as connection:
                connection.request('HEAD', '/')
                connection.getresponse()
        except (ConnectionError, TimeoutError):
            return False
        try:
            self.winrm_shell().run(['whoami'])
        except (WinRMOperationTimeoutError, WinRmUnauthorized):
            return False
        return True

    def close(self):
        self._smb_connection_pool.close()
        if self._winrm_shell is not None:
            self._winrm_shell.close()
            self._winrm_shell = None
        self._traffic_capture = None

    @functools.lru_cache()
    def home(self, user=None) -> SmbPath:
        if user is not None:
            user = self._get_local_user(user)
            profile = user.profile()
            return profile.local_path
        return self.path(self._env_vars()['USERPROFILE'])

    def tmp(self) -> SmbPath:
        return self.path('C:\\', 'Windows', 'Temp')

    def path(self, *parts) -> SmbPath:
        return SmbPath(self._smb_connection_pool, *parts)

    @property  # TODO: Make it a simple method
    def traffic_capture(self):
        if self._traffic_capture is None:
            path = self.path('c:\\') / 'NetworkTrafficCapture'
            self._traffic_capture = WindowsTrafficCapture(path, self.winrm_shell())
        return self._traffic_capture

    def Popen(self, command):
        return self.winrm_shell().Popen(command)

    def run(
            self,
            command,
            input: Optional[bytes] = None,
            timeout_sec: float = 60,
            check=True,
            ):
        return self.winrm_shell().run(
            command,
            input=input,
            timeout_sec=timeout_sec,
            check=check,
            )

    def winrm_shell(self):
        """Lazy shell creation."""
        if self._winrm_shell is None:
            self._winrm_shell = WinRMShell(self.winrm)
        return self._winrm_shell

    def get_datetime(self) -> datetime:
        started_at = time.monotonic()
        result = self._get_os()
        delay_sec = time.monotonic() - started_at
        remote_time: datetime = result['LocalDateTime']
        if remote_time.tzinfo is None:
            raise RuntimeError("Windows returned datetime without a timezone")
        _logger.debug("%r: Time %r, round trip %.3f sec", self, remote_time, delay_sec)
        return remote_time

    def set_datetime(self, new_time: datetime) -> None:
        if new_time.tzinfo is None:
            raise ValueError(f'Expected datetime with timezone, got: {new_time!r}')
        machine_timezone = self.get_datetime().tzinfo
        localized = new_time.astimezone(machine_timezone)
        started_at = time.monotonic()
        self.winrm.wsman_invoke('Win32_OperatingSystem', {}, 'SetDateTime', {'LocalDateTime': new_time})
        delay_sec = time.monotonic() - started_at
        _logger.debug(
            "%r: New time %r (their timezone), round trip %.3f sec",
            self, localized, delay_sec)

    def _clear_and_enable_logs(self):
        return  # FT-1204: Disable logs collection temporary

    def download_system_logs(self, target_local_dir):
        """Collect Windows event log files from default location.

        See: https://learn.microsoft.com/en-us/windows/win32/eventlog/eventlog-key
        """
        # The event log files are currently open in another process, which is preventing them
        # from being directly processed by tar utility
        self.run(r'mkdir C:\EventLog', check=False)
        self.run(r'del /F /S /Q C:\EventLog\*.evtx')
        self.run(r'copy /Y /B %SYSTEMROOT%\System32\winevt\Logs\*.evtx C:\EventLog')
        # Sometimes, under high load on test hosts, the archiving may take longer.
        self.run(r'tar -caf C:\EventLog\eventlog.zip -C C:\EventLog *.evtx', timeout_sec=120)
        copy_file(self.path(r'C:\EventLog\eventlog.zip'), target_local_dir / 'eventlog.zip')

    def program_data_dir(self):
        return self.path(self._env_vars()['PROGRAMDATA'])

    def program_files_dir(self):
        return self.path(self._env_vars()['PROGRAMFILES'])

    @functools.lru_cache()
    def _env_vars(self):
        outcome = self.run('set')
        decoded = outcome.stdout.decode()  # Take encoding from the shell.
        lines = decoded.splitlines()
        r = {}
        for line in lines:
            name, value = line.split('=', 1)
            r[name.upper()] = value
        return r

    def system_profile_dir(self):
        return self.path(self._system_profile().local_path)

    @functools.lru_cache()
    def _system_profile(self):
        return UserProfile(self.winrm, 'S-1-5-18')

    @functools.lru_cache()
    def _get_local_admin(self):
        return self._get_local_user('Administrator')

    def _get_local_domain_name(self):
        return self._get_os()['CSName']

    @functools.lru_cache()
    def _get_local_user(self, name):
        domain = self._get_local_domain_name()
        return UserAccount(self.winrm, domain + '\\' + name)

    def _is_smb_working(self) -> bool:
        try:
            self.tmp().exists()
        except ConnectionError:
            _logger.info("WinRM is working, but SMB is not ready yet")
            return False
        return True

    def is_ready(self):
        return self._winrm_is_working() and self._is_smb_working()

    def reboot(self):
        """Reboot and return when OS has been rebooted."""
        traffic_capture_initial_running_state = self.traffic_capture.is_running()
        # Last boot-up time is used as it, by definition, should change only if reboot occurred.
        self.traffic_capture.stop()
        boot_up_time_before = self._get_os()['LastBootUpTime']
        self.winrm.wsman_invoke('Win32_OperatingSystem', {}, 'Reboot', {})
        self.close()
        _logger.info("Sleep while definitely rebooting.")
        time.sleep(5)
        # Windows may respond for several seconds before it goes offline.
        time_to_reboot = 60
        started_at = time.monotonic()
        while time.monotonic() - started_at <= time_to_reboot:
            try:
                boot_up_time_after = self._get_os()['LastBootUpTime']
            except ConnectionError:
                _logger.debug("Still offline; reconnect in a while.")
                time.sleep(1)
            else:
                if boot_up_time_after != boot_up_time_before:
                    _logger.info("Rebooted.")
                    break
                _logger.debug("Still online; sleep while OS is definitely rebooting.")
                time.sleep(5)
        else:
            raise RuntimeError(f"Can't reboot the machine after {time_to_reboot}")
        if traffic_capture_initial_running_state:
            self.traffic_capture.start()

    def kill_all_by_name(self, executable_name):
        if executable_name.endswith('.exe'):
            executable_name = executable_name[:-4]
        with suppress(CalledProcessError):
            self.run([
                'taskkill',
                '/f',  # forcefully terminate the process(es)
                # Commented out for behaviour be exactly the same as under posix:
                # '/t',  # terminates the specified process and any child processes which were started by it
                '/im',  # specifies the image name of the process to be terminated
                executable_name + '.exe',
                ])

    def get_pid_by_name(self, executable_name: str) -> int:
        for _ in range(2):
            try:
                return self._get_pid_by_name(executable_name)
            except EmptyStdout:
                _logger.error("tasklist.exe returned an empty stdout")
        else:
            raise FileNotFoundError(f"Cannot found pid by name {executable_name!r}")

    def _get_pid_by_name(self, executable_name: str) -> int:
        if executable_name.endswith('.exe'):
            executable_name = executable_name[:-4]
        command = [
            'tasklist',
            '-svc',
            '-nh',
            '-fi', f'imagename eq {executable_name}.exe',
            ]
        result = self.run(command)
        if b'No tasks are running which match the specified criteria' in result.stdout:
            raise FileNotFoundError(f"Process {executable_name} not found")
        if not result.stdout:
            raise EmptyStdout()
        [*_, pid, _] = result.stdout.split()
        try:
            return int(pid.decode())
        except ValueError:
            _logger.error(
                "Cannot found pid by name.\n"
                "Command: %s\nOutput:\n%s",
                ' '.join(command), result.stdout.decode('utf-8'))
            raise FileNotFoundError(f"Cannot found pid by name {executable_name!r}")

    def _mounted_fake_disks(self):
        images = self.path('c:\\').glob('?.vhdx')
        return [self._mount_path(image.stem) for image in images]

    def is_fake_disk_mounted(self, letter):
        return self._mount_path(letter) in self._mounted_fake_disks()

    def mount_smb_share(self, mount_point, path, username, password):
        _logger.debug("Mount SMB shares not implemented yet in Windows")

    def dismount_smb_share(self, mount_point, lazy=True):
        _logger.debug("Dismount SMB shares not implemented yet in Windows")

    def fs_root(self) -> SmbPath:
        return self.path('C:\\')

    def volumes(self):
        mount_point_iter = self.winrm.wsman_all('Win32_MountPoint')
        volume_iter = self.winrm.wsman_all('Win32_Volume')
        volume_list = list(volume_iter)
        result = {}
        for _, mount_point in mount_point_iter:
            # Rely on fact that single identifying selector of `Directory` is its name.
            dir_path = self.path(mount_point['Directory'].selectors['Name'])
            for volume_ref, volume in volume_list:
                if volume_ref == mount_point['Volume']:
                    if volume['FreeSpace'] is None:
                        _logger.info("No disk: %s", dir_path)
                    else:
                        free_space = int(volume['FreeSpace'])
                        capacity = int(volume['Capacity'])
                        result[dir_path] = Disk(capacity, free_space)
                    break
            else:
                _logger.info("No disk: %s", dir_path)
        return result

    def create_file(self, file_path, file_size_b):
        try:
            file_path.unlink()
        except FileNotFoundError:
            _logger.info("Space holder does not exist")
        self.run(['fsutil', 'file', 'createNew', file_path, file_size_b])

    def file_md5(self, path):
        try:
            result = self.run(['CertUtil', '-hashfile', path, 'md5'])
        except CalledProcessError as e:
            if not (e.returncode == 0x80070002 or e.returncode == 0x80070005):
                raise e
            if path.is_dir():
                raise IsADirectoryError(errno.EISDIR, "Trying to get MD5 of dir.")
            else:
                raise PermissionError()
        output = result.stdout.decode()
        # We need to match 47 symbols, because windows 8.1 returns MD5 with spaces.
        match = re.search(r'\b[0-9a-fA-F(\ )]{32,47}\b', output)
        if match is None:
            raise RuntimeError('Cannot get MD5 of {}:\n{}'.format(path, output))
        # Extra white spaces must be deleted for stability of the tests.
        return match.group().replace(" ", "")

    def folder_contents_size(self, folder):
        run_result = self.run([
            'dir',
            '/a',  # Include system and hidden files
            '/s',  # Recursive
            folder,
            ])
        output_lines = run_result.stdout.decode('ascii').splitlines()
        [_, _, result, _] = output_lines[-2].split()
        return int(result.replace(',', ''))

    def files_size_sum(self, folder: SmbPath, extension: str) -> int:
        try:
            run_result = self.run([
                'dir',
                '/a',  # Include system and hidden files
                '/s',  # Recursive
                folder / f'*{extension}',
                ])
        except CalledProcessError as e:
            if e.stderr == b'File Not Found\r\n':
                return 0
            raise e
        output_lines = run_result.stdout.decode('ascii').splitlines()
        [_, _, result, _] = output_lines[-2].split()
        return int(result.replace(',', ''))

    @functools.lru_cache()
    def source_address(self):
        """Get client source IP from WinRM shell."""
        return self.winrm_shell().client_ip

    def service(self, name):
        return _WindowsService(self.winrm, name)

    def dummy_service(self):
        return self.service('Spooler')  # Spooler manages printers.

    def _create_vhdx_file(self, letter: str, disk_mb: int) -> Path:
        script_template = 'CREATE VDISK file={image_path} MAXIMUM={disk_mb} TYPE={type}' '\r\n'
        image_path = self.path('C:\\{}.vhdx'.format(letter))
        script = script_template.format(image_path=image_path, type='EXPANDABLE', disk_mb=disk_mb)
        _logger.debug('Creating VHDX file with diskpart script:\n%s', script)
        script_path = self.path(f'C:\\{letter}.diskpart.txt')
        script_path.write_text(script)
        timeout_sec = 10 + 0.05 * disk_mb
        # Error originate in VDS -- Virtual Disk Service.
        # See: https://msdn.microsoft.com/en-us/library/dd208031.aspx
        try:
            self.run(['diskpart', '/s', script_path], timeout_sec=timeout_sec)
        except CalledProcessError as e:
            if e.returncode != 0x80070057:
                raise
            message_multiline = e.stdout.decode().rstrip().rsplit('\r\n\r\n')[-1]
            message_oneline = message_multiline.replace('\r\n', ' ')
            raise OSError(errno.EINVAL, message_oneline)
        return image_path

    def dismount_fake_disk(self, mount_point):
        letter = self._mount_letter(mount_point)
        image_path = self.path('C:\\{}.vhdx'.format(letter))
        # If disk is not mounted - no error is produced.
        self.winrm.wsman_invoke(
            cls='wmi/Root/Microsoft/Windows/Storage/MSFT_DiskImage',
            selectors={'ImagePath': str(image_path), 'StorageType': '3'},  # 3 is VHDX
            method_name='Dismount',
            params={},
            )
        _logger.debug("Delete virtual disk file: %s", image_path)
        image_path.unlink()

    def mount_fake_disk(self, letter, size_bytes):
        """Make virtual disk and mount it.

        See: https://docs.microsoft.com/en-us/previous-versions/windows/desktop/stormgmt/windows-storage-management-api-portal
        """
        disk_mb = int(math.ceil(size_bytes / 1024 / 1024)) + 2  # 2 MB is for MBR/GPT headers.
        image_path = self._create_vhdx_file(letter, disk_mb)
        image_selectors = {'ImagePath': str(image_path), 'StorageType': '3'}  # 3 is VHDX
        self.winrm.wsman_invoke(
            cls='wmi/Root/Microsoft/Windows/Storage/MSFT_DiskImage',
            selectors=image_selectors,
            method_name='Mount',
            params={},
            )
        disk_image = self.winrm.wsman_get(
            'wmi/Root/Microsoft/Windows/Storage/MSFT_DiskImage', image_selectors)
        [[disk_reference, _]] = self.winrm.wsman_select(
            'wmi/Root/Microsoft/Windows/Storage/MSFT_Disk', {'Number': disk_image['Number']})
        self.winrm.wsman_invoke(
            cls=disk_reference.uri,
            selectors=disk_reference.selectors,
            method_name='Initialize',
            params={'PartitionStyle': 1},  # 1 is MBR
            )
        self.winrm.wsman_invoke(
            cls=disk_reference.uri,
            selectors=disk_reference.selectors,
            method_name='CreatePartition',
            params={'Size': size_bytes, 'MbrType': 7},  # 7 is NTFS
            )
        [[partition_reference, _]] = self.winrm.wsman_associated(
            disk_reference.uri, disk_reference.selectors, result_cls_name='MSFT_Partition')
        [[volume_reference, _]] = self.winrm.wsman_associated(
            partition_reference.uri, partition_reference.selectors, result_cls_name='MSFT_Volume')
        try:
            self.winrm.wsman_invoke(
                cls=volume_reference.uri,
                selectors=volume_reference.selectors,
                method_name='Format',
                params={'FileSystem': 'NTFS', 'Full': False},  # Full: False means quick format
                )
        except WmiInvokeFailed as e:
            if e.return_value == 5:
                # Sometimes volume format can fail with "Invalid parameters" error. The workaround is
                # to mount partition into a folder (not into a drive to avoid format prompt window)
                # and format again.
                temporary_access_path = self.tmp() / f'AccessPath{letter}'
                temporary_access_path.rmtree(ignore_errors=True)
                temporary_access_path.mkdir()
                self.winrm.wsman_invoke(
                    cls=partition_reference.uri,
                    selectors=partition_reference.selectors,
                    method_name='AddAccessPath',
                    params={'AccessPath': str(temporary_access_path)},
                    )
                self.winrm.wsman_invoke(
                    cls=volume_reference.uri,
                    selectors=volume_reference.selectors,
                    method_name='Format',
                    params={'FileSystem': 'NTFS', 'Full': False},  # Full: False means quick format
                    )
                # If access path is not removed - directory deletion will fail.
                self.winrm.wsman_invoke(
                    cls=partition_reference.uri,
                    selectors=partition_reference.selectors,
                    method_name='RemoveAccessPath',
                    params={'AccessPath': str(temporary_access_path)},
                    )
                temporary_access_path.rmtree()
            else:
                raise
        # Assign drive letter after format operation to avoid format prompt window.
        self.winrm.wsman_invoke(
            cls=partition_reference.uri,
            selectors=partition_reference.selectors,
            method_name='AddAccessPath',
            params={'AccessPath': f'{letter}:'},
            )
        return self._mount_path(letter)

    def _update_storage_cache(self):
        self.winrm.wsman_invoke(
            "wmi/Root/Microsoft/Windows/Storage/MSFT_StorageSetting",
            selectors={},
            method_name='UpdateHostStorageCache',
            params={},
            )

    def list_mounted_disks(self) -> Mapping[SmbPath, str]:
        msft_partitions = self.winrm.wsman_all('wmi/Root/Microsoft/Windows/Storage/MSFT_Partition')
        result = {}
        for _, data in msft_partitions:
            try:
                [access_path, _] = data['AccessPaths']
            except ValueError:
                continue
            drive_letter = data['DriveLetter']
            if not drive_letter:
                _logger.debug("%r is not mounted as disk", access_path)
                continue
            mount_point = self.path(access_path)
            result[mount_point] = f'{drive_letter}:'
        return result

    def _list_disks_without_partition(self):
        msft_disks = self.winrm.wsman_all('wmi/Root/Microsoft/Windows/Storage/MSFT_Disk')
        disks_without_partition = []
        for disk_reference, disk_data in msft_disks:
            if disk_data['NumberOfPartitions'] == '0':
                disks_without_partition.append(disk_reference)
        return disks_without_partition

    def _get_newly_attached_disk(self):
        # FT-1603: Force rescan disks in case Windows didn't add or remove it
        self._update_storage_cache()
        return self._wait_for_newly_attached_disk_appears()

    def mount_disk(self, letter):
        disk_reference = self._get_newly_attached_disk()
        self.winrm.wsman_invoke(
            cls=disk_reference.uri,
            selectors=disk_reference.selectors,
            method_name='Initialize',
            params={'PartitionStyle': 1},  # 1 is MBR
            )
        self.winrm.wsman_invoke(
            cls=disk_reference.uri,
            selectors=disk_reference.selectors,
            method_name='CreatePartition',
            params={'UseMaximumSize': True, 'MbrType': 7},  # 7 is NTFS
            )
        [[partition_reference, _]] = self.winrm.wsman_associated(
            disk_reference.uri, disk_reference.selectors, result_cls_name='MSFT_Partition')
        [[volume_reference, _]] = self.winrm.wsman_associated(
            partition_reference.uri, partition_reference.selectors, result_cls_name='MSFT_Volume')
        self.winrm.wsman_invoke(
            cls=volume_reference.uri,
            selectors=volume_reference.selectors,
            method_name='Format',
            params={'FileSystem': 'NTFS', 'Full': False},  # Full: False means quick format
            )
        # Assign drive letter after format operation to avoid format prompt window.
        self.winrm.wsman_invoke(
            cls=partition_reference.uri,
            selectors=partition_reference.selectors,
            method_name='AddAccessPath',
            params={'AccessPath': f'{letter}:'},
            )
        return self.path(f'{letter}:/')

    @contextmanager
    def mount_disabled(self, mount_point):
        msft_partitions = self.winrm.wsman_all('wmi/Root/Microsoft/Windows/Storage/MSFT_Partition')
        for reference, data in msft_partitions:
            try:
                [access_path, _] = data['AccessPaths']
            except ValueError:
                continue
            if self.path(access_path) == mount_point:
                partition_reference = reference
                break
        else:
            raise RuntimeError(f"Partition with access path {mount_point!r} not found")
        self.winrm.wsman_invoke(
            cls=partition_reference.uri,
            selectors=partition_reference.selectors,
            method_name='SetAttributes',
            params={'IsHidden': True, 'IsActive': False},
            )
        yield
        self.winrm.wsman_invoke(
            cls=partition_reference.uri,
            selectors=partition_reference.selectors,
            method_name='SetAttributes',
            params={'IsHidden': False, 'IsActive': True},
            )

    def set_disk_quota(self, letter, quota_bytes):
        [[disk_ref, disk_obj]] = self.winrm.wsman_select(
            'Win32_QuotaSetting', {'VolumePath': f'{letter}:\\\\'})
        # State '2' means that quotas are tracked and enforced on this volume
        # More info: https://docs.microsoft.com/en-us/previous-versions/windows/desktop/wmipdskq/win32-quotasetting
        self.winrm.wsman_put(*disk_ref, {'State': '2', 'DefaultLimit': quota_bytes})
        return disk_obj

    def _hosts_file(self):
        env = self._env_vars()
        windows_dir = self.path(env['SYSTEMROOT'])
        hosts_file = windows_dir / 'System32' / 'drivers' / 'etc' / 'hosts'
        return hosts_file

    def unzip(self, archive_path, dest_dir):
        dest_dir.mkdir(parents=True, exist_ok=True)
        self.run([
            'tar',
            '-x',  # -x is for "extract"
            '-f', archive_path,  # -f is for "filename" (of archive)
            '-C', dest_dir,  # -C is for "change dir"; i.e. destination
            ])

    @functools.lru_cache()
    def _get_os_cached(self):
        return self._get_os()

    def arch(self):
        return self._get_os_cached()["OSArchitecture"]

    def _version(self):
        return tuple(int(v) for v in self._get_os_cached()["Version"].split('.'))

    def _get_os(self):
        return self.winrm.wsman_get('Win32_OperatingSystem', {})

    _share_description = 'NX Functional Tests share'

    def create_smb_share(self, name, path, user):
        sid = self._get_local_user(user).sid
        self.winrm.wsman_invoke('Win32_Share', {}, 'Create', {
            'Path': str(path),
            'Name': name,
            'Type': 0,  # 0 for disk, 1 for printer, 2 for device, 3 for IPC...
            'Description': self._share_description,
            'Access': {
                '@xmlns': {
                    'ace': 'http://schemas.microsoft.com/wbem/wsman/1/wmi/root/cimv2/Win32_ACE',
                    'sd': 'http://schemas.microsoft.com/wbem/wsman/1/wmi/root/cimv2/Win32_SecurityDescriptor',
                    'trustee': 'http://schemas.microsoft.com/wbem/wsman/1/wmi/root/cimv2/Win32_Trustee',
                    },
                '@xsi:type': 'sd:Win32_SecurityDescriptor_Type',
                'sd:DACL': [
                    {
                        '@xsi:type': 'ace:Win32_ACE_Type',
                        'ace:AceFlags': '0',
                        # The mask was taken from WMI response of a manually
                        # created share with the Read and Write boxes checked.
                        'ace:AccessMask': 0x1301bf,  # Read/write.
                        'ace:AceType': 0,  # 0 allows, 1 denies.
                        'ace:Trustee': {
                            '@xsi:type': 'trustee:Win32_Trustee_Type',
                            'trustee:SID': sid.for_xmldict,
                            },
                        },
                    ],
                },
            })

    def create_iscsi_target(self, size, alias):
        _logger.debug("Creating iSCSI targets is not yet implemented in Windows")

    def _create_volume(self, disk_selectors):
        self.winrm.wsman_invoke(
            'wmi/Root/Microsoft/Windows/Storage/MSFT_Disk',
            selectors=disk_selectors,
            method_name='Initialize',
            params={'PartitionStyle': 1},  # MBR
            )
        self.winrm.wsman_invoke(
            'wmi/Root/Microsoft/Windows/Storage/MSFT_Disk',
            selectors=disk_selectors,
            method_name='CreatePartition',
            params={
                'UseMaximumSize': True,
                'AssignDriveLetter': True,
                })
        [[partition_reference, _]] = self.winrm.wsman_associated(
            'wmi/Root/Microsoft/Windows/Storage/MSFT_Disk',
            selectors=disk_selectors,
            result_cls_name='MSFT_Partition',
            )
        [[volume_reference, _]] = self.winrm.wsman_associated(
            'wmi/Root/Microsoft/Windows/Storage/MSFT_Partition',
            selectors=partition_reference.selectors,
            result_cls_name='MSFT_Volume',
            )
        output = self.winrm.wsman_invoke(
            'wmi/Root/Microsoft/Windows/Storage/MSFT_Volume',
            selectors=volume_reference.selectors,
            method_name='Format',
            params={'FileSystem': 'NTFS'},
            )
        volume_uri = resolve_resource_uri('wmi/root/microsoft/windows/storage/MSFT_Volume')
        letter = output[volume_uri + ':FormattedVolume'][volume_uri + ':DriveLetter']
        return self._mount_path(letter)

    def _mount_path(self, letter):
        return self.path(f'{letter}:\\')

    def _mount_letter(self, mount_point):
        for letter in string.ascii_uppercase:
            if self._mount_path(letter) == mount_point:
                return letter
        raise ValueError(f"Cannot get letter from mount point {mount_point}")

    def mount_iscsi_disk(self, address, target_name) -> SmbPath:
        self.winrm.wsman_invoke(
            'wmi/Root/Microsoft/Windows/Storage/MSFT_iSCSITargetPortal',
            selectors={},
            method_name='New',
            params={'TargetPortalAddress': address},
            )
        session = self.winrm.wsman_invoke(
            'wmi/Root/Microsoft/Windows/Storage/MSFT_iSCSITarget',
            selectors={},
            method_name='Connect',
            params={
                'NodeAddress': target_name,
                'TargetPortalAddress': address,
                },
            )
        target_ns = resolve_resource_uri('wmi/root/microsoft/windows/storage/MSFT_iSCSITarget')
        session_ns = resolve_resource_uri('wmi/root/microsoft/windows/storage/MSFT_iSCSISession')
        session_id = session[target_ns + ':CreatediSCSISession'][session_ns + ':SessionIdentifier']
        started_at = time.monotonic()
        while True:
            disks = list(self.winrm.wsman_associated(
                'wmi/Root/Microsoft/Windows/Storage/MSFT_iSCSISession',
                selectors={'SessionIdentifier': session_id},
                result_cls_name='MSFT_Disk',
                ))
            if disks:
                break
            if time.monotonic() - started_at > 5:
                raise TimeoutError("iSCSI disk didn't appear after timeout.")
            _logger.debug("Wait for iSCSI disk to appear.")
            time.sleep(1)
        [[disk_reference, _]] = disks
        return self._create_volume(disk_reference.selectors)

    def dismount_iscsi_disk(self, target_iqn):
        [[target_reference, _]] = self.winrm.wsman_select(
            'wmi/Root/Microsoft/Windows/Storage/MSFT_iSCSITarget',
            selectors={'NodeAddress': target_iqn},
            )
        [[session_reference, _]] = self.winrm.wsman_associated(
            'wmi/Root/Microsoft/Windows/Storage/MSFT_iSCSITarget',
            selectors=target_reference.selectors,
            result_cls_name='MSFT_iSCSISession',
            )
        # To remove iSCSI target, associated disk (if any) must be offline.
        for disk_reference, _ in self.winrm.wsman_associated(
            'wmi/Root/Microsoft/Windows/Storage/MSFT_iSCSISession',
            selectors=session_reference.selectors,
            result_cls_name='MSFT_Disk',
                ):
            self.winrm.wsman_invoke(
                'wmi/Root/Microsoft/Windows/Storage/MSFT_Disk',
                selectors=disk_reference.selectors,
                method_name='Offline',
                params={},
                )
        self.winrm.wsman_invoke(
            'wmi/Root/Microsoft/Windows/Storage/MSFT_iSCSITarget',
            selectors={'NodeAddress': target_iqn},
            method_name='Disconnect',
            params={},
            )
        self.winrm.wsman_invoke(
            'wmi/Root/Microsoft/Windows/Storage/MSFT_iSCSITarget',
            selectors={'NodeAddress': target_iqn},
            method_name='Update',
            params={},
            )

    def _escape(self, arg):
        return '"'.join('"' + part + '"' for part in arg.split('"'))

    def _validate_user_name(self, name):
        for invalid_character in r'"/\[]:;|=,+*?<>@':
            if invalid_character in name:
                raise ValueError(
                    "User name contains invalid character {}: {}".format(
                        name, invalid_character))

    def create_user(self, name, password='', exist_ok=False):
        if password == '':
            self._allow_blank_password_use()
        # A user cannot be created via WMI.
        # `net user` says "syntax error" if user name is invalid.
        self._validate_user_name(name)
        try:
            self.run('net user {} {} /add /comment:{}'.format(
                self._escape(name), self._escape(password),
                self._escape(self._user_description),
                ))
        except CalledProcessError as e:
            if exist_ok and b'already exists' in (e.stdout + e.stderr).lower():
                _logger.debug("User already exists: {}".format(name))
            else:
                raise
        else:
            _logger.debug("User has been created: {}".format(name))

    def disable_user(self, name):
        self._validate_user_name(name)
        self.run(f'net user {self._escape(name)} /active:no')
        _logger.debug("User has been disabled: %s", name)

    def _change_access(self, path, user, allow_access=None):
        user_sid = self._get_local_user(user).sid
        admin_sid = self._get_local_admin().sid
        self.winrm.wsman_invoke('Win32_Directory', {'Name': str(path)}, 'ChangeSecurityPermissions', {
            'SecurityDescriptor': {
                '@xmlns': {
                    'ace': 'http://schemas.microsoft.com/wbem/wsman/1/wmi/root/cimv2/Win32_ACE',
                    'sd': 'http://schemas.microsoft.com/wbem/wsman/1/wmi/root/cimv2/Win32_SecurityDescriptor',
                    'trustee': 'http://schemas.microsoft.com/wbem/wsman/1/wmi/root/cimv2/Win32_Trustee',
                    },
                '@xsi:type': 'sd:Win32_SecurityDescriptor_Type',
                'sd:DACL': [
                    {
                        '@xsi:type': 'ace:Win32_ACE_Type',
                        # This makes Windows apply access rights recursively to all subdirectories.
                        'ace:AceFlags': 3,  # OBJECT_INHERIT_ACE | CONTAINER_INHERIT_ACE.
                        # The mask was taken from WMI response of a manually
                        # created share with the Read and Write boxes checked.
                        'ace:AccessMask': 0x1301bf,  # Read/write.
                        'ace:AceType': 0 if allow_access else 1,  # 0 allows, 1 denies.
                        'ace:Trustee': {
                            '@xsi:type': 'trustee:Win32_Trustee_Type',
                            'trustee:SID': user_sid.for_xmldict,
                            },
                        },
                    {
                        '@xsi:type': 'ace:Win32_ACE_Type',
                        'ace:AceFlags': 3,  # OBJECT_INHERIT_ACE | CONTAINER_INHERIT_ACE.
                        # The mask was taken from WMI response of a manually
                        # created share with the Read and Write boxes checked.
                        'ace:AccessMask': 0x1f01ff,  # Full access.
                        'ace:AceType': 0,  # 0 allows, 1 denies.
                        'ace:Trustee': {
                            '@xsi:type': 'trustee:Win32_Trustee_Type',
                            'trustee:SID': admin_sid.for_xmldict,
                            },
                        },
                    ],
                },
            'Option': 4,  # CHANGE_DACL_SECURITY_INFORMATION.
            })

    def allow_access(self, path, user):
        self._change_access(path, user, allow_access=True)

    def allow_access_for_everyone(self, path):
        self._change_access(path, 'Everyone', allow_access=True)

    def deny_access(self, path, user):
        self._change_access(path, user, allow_access=False)

    # This registry key is used to limit users with blank password to only local
    # system access. If remote access is needed (i.e. smb), set 0. Default is 1.
    _limit_blank_password_use_registry_path = (
        r'HKLM\SYSTEM\CurrentControlSet\Control\Lsa',
        'LimitBlankPasswordUse')

    def _allow_blank_password_use(self):
        self.registry.set_dword(*self._limit_blank_password_use_registry_path, data=0)

    def _restrict_blank_password_use(self):
        self.registry.set_dword(*self._limit_blank_password_use_registry_path, data=1)

    def _get_diagnostic_report(self):
        r = []
        r.append(self._handle_command_with_timeout('time /t', 10))
        r.append(self._handle_command_with_timeout('systeminfo', 10))
        r.append(self._handle_command_with_timeout('ipconfig /all', 10))
        r.append(self._handle_command_with_timeout('ipconfig /displaydns', 10))
        r.append(self._handle_command_with_timeout('route print /4', 10))
        r.append(self._handle_command_with_timeout('arp /a', 10))
        r.append(self._handle_command_with_timeout('netstat /n', 10))
        r.append(self._handle_command_with_timeout('tasklist /fo list /v', 20))
        r.append(self._handle_command_with_timeout('tasklist /fo list /svc', 20))
        r.append(self._handle_command_with_timeout('schtasks /query /fo list /v', 30))
        # The "net user" commands exits with status 1 often, but yields the result.
        r.append(self._handle_command_with_timeout('net user || echo Exit %ErrorLevel%', 30))
        r.append(self._handle_command_with_timeout('fsutil volume list', 30))
        r.append(self._handle_command_with_timeout('sc query type= service state= all', 30))
        return b'\n'.join(r)

    def get_cpu_name(self):
        return self.winrm.wsman_get('Win32_Processor', {'DeviceID': 'CPU0'})['Name']

    def get_process_thread_count(self, pid):
        process = _ProcessCounter(self._performance_counter_engine, pid).get_last()
        return int(process['ThreadCount'])

    def get_ram_usage(self, pid):
        process = _ProcessCounter(self._performance_counter_engine, pid).get_last()
        system_info = self._get_os()
        process_bytes = int(process['WorkingSet'])
        process_peak_bytes = int(process['WorkingSetPeak'])
        system_free_kbytes = int(system_info['FreePhysicalMemory'])
        system_total_kbytes = int(system_info['TotalVisibleMemorySize'])
        process_used = process_bytes / 1024 / system_total_kbytes
        system_used_kbytes = system_total_kbytes - system_free_kbytes
        system_used = system_used_kbytes / system_total_kbytes
        return RamUsage(
            process_used,
            system_used,
            process_bytes,
            system_used_kbytes * 1024,
            process_peak_bytes,
            )

    def _get_used_memory_mbytes(self):
        system_info = self._get_os()
        system_free_kbytes = int(system_info['FreePhysicalMemory'])
        system_total_kbytes = int(system_info['TotalVisibleMemorySize'])
        return (system_total_kbytes - system_free_kbytes) / 1024

    def _start_ram_load(self, ram_mbytes):
        # Avoid license agreement pop up.
        self.registry.create_key(r'HKCU\Software\Sysinternals')
        self.registry.set_dword(r'HKCU\Software\Sysinternals', 'EulaAccepted', 1)
        self.Popen(
            f'start c:\\Sysinternals\\Testlimit64.exe -d {ram_mbytes} -c 1'
            ' & ping -n 120 127.0.0.1 >nul'  # Classical CMD sleep.
            ' & taskkill /f /im Testlimit64.exe')

    def stop_ram_load(self):
        self.kill_all_by_name('Testlimit64.exe')

    def close_all_smb_sessions(self):
        for _, fields in self.winrm.wsman_all('wmi/Root/Microsoft/Windows/SMB/MSFT_SmbSession'):
            self.winrm.wsman_invoke(
                'wmi/Root/Microsoft/Windows/SMB/MSFT_SmbSession',
                selectors={'SessionId': fields['SessionId']},
                method_name='ForceClose',
                params={})

    @functools.lru_cache()
    def _get_logical_processor_count(self) -> int:
        cpu = self.winrm.wsman_get('Win32_Processor', {'DeviceID': 'CPU0'})
        return int(cpu['NumberOfLogicalProcessors'])

    def _list_counter_samples(self, counter: str, interval: int, sample_count: int):
        additional_timeout = 10
        counters = run_powershell_script(
            self._winrm_shell,
            'Get-Counter -Counter $counter -SampleInterval $interval -MaxSamples $sample_count',
            dict(
                interval=interval,
                sample_count=sample_count,
                counter=counter,
                ),
            timeout_sec=additional_timeout + interval * sample_count,
            )
        result = []
        for counter_dict in counters:
            counter_value = counter_dict['Readings']
            [_, processor_time, *_] = counter_value.splitlines()
            result.append(float(processor_time))
        return result

    def list_total_cpu_usage(self, sample_interval_sec, sample_count):
        counter = r'\Processor(_Total)\% Processor Time'
        result = []
        cpu_usage_samples = self._list_counter_samples(counter, sample_interval_sec, sample_count)
        for processor_time in cpu_usage_samples:
            result.append(float(processor_time) / 100)
        return result

    def list_process_cpu_usage(self, pid, sample_interval_sec, sample_count):
        cores_count = self._get_logical_processor_count()
        process_name = self._get_process_name(pid)
        counter = fr'\Process({process_name})\% Processor Time'
        result = []
        cpu_usage_samples = self._list_counter_samples(counter, sample_interval_sec, sample_count)
        for processor_time in cpu_usage_samples:
            result.append(float(processor_time) / 100 / cores_count)
        return result

    def _get_process_name(self, pid: int):
        [[_, data]] = self.winrm.wsman_select('Win32_Process', {'ProcessId': str(pid)})
        [process_name, _] = data['Name'].split('.')
        return process_name

    def _start_cpu_load(self):
        for _ in range(self._get_logical_processor_count()):
            start_powershell_script(self.winrm_shell(), self._cpu_load_script, {})

    def _stop_cpu_load(self):
        result = self.winrm.wsman_select('Win32_Process', {'Name': 'powershell.exe'})
        for reference, body in result:
            process_command_line = extract_script_from_command_line(body['CommandLine'])
            if self._cpu_load_script not in process_command_line:
                continue
            pid = reference.selectors['Handle']
            try:
                self.run(['taskkill', '/f', '/pid', pid])
            except CalledProcessError:
                _logger.error("While killing process %s and error occurred.", str(pid))

    def compact(self):
        start_at = time.monotonic()
        logging.info("Compacting the image ...")
        self.run(['C:\\Sysinternals\\sdelete.exe', '/accepteula', '-z', 'C:'], timeout_sec=600)
        duration = time.monotonic() - start_at
        logging.info("Compacting took %s sec", duration)

    def add_trusted_certificate(self, cert_path):
        certs_dir = self.path('C:\\FT\\certs')
        certs_dir.mkdir(parents=True, exist_ok=True)
        trusted_cert_path = certs_dir / cert_path.name
        copy_file(cert_path, trusted_cert_path)
        self.run(['CertUtil', '-addStore', 'root', trusted_cert_path])

    def get_cpu_usage(self) -> float:
        # See: https://wutils.com/wmi/root/cimv2/win32_perfformatteddata_perfos_processor/#percentprocessortime_properties
        [[_, data]] = self.winrm.wsman_select('Win32_PerfFormattedData_PerfOS_Processor', {'Name': '_Total'})
        return float(data['PercentProcessorTime']) / 100

    def get_cpu_time_process(self, pid):
        process = _ProcessCounter(self._performance_counter_engine, pid).get_last()
        return float(process['PercentProcessorTime']) * self._tick

    def get_io_time(self):
        result = []
        for values in _DisksCounter(self._performance_counter_engine).get_all():
            io_info = DiskIoInfo(
                name=values['Name'].replace(' ', '_'),
                reading_sec=float(values['PercentDiskReadTime']) * self._tick,
                writing_sec=float(values['PercentDiskWriteTime']) * self._tick,
                read_bytes=int(values['DiskReadBytesPersec']),
                write_bytes=int(values['DiskWriteBytesPersec']),
                read_count=int(values['DiskReadsPersec']),
                write_count=int(values['DiskWritesPersec']),
                )
            result.append(io_info)
        return result

    def get_open_files_count(self, pid):
        command = f'c:\\SysInternals\\handle64.exe /accepteula -nobanner -s -p {pid}'
        output = self.run(command).stdout.decode()
        output_lines: Collection[str] = output.split('\n')
        for line in output_lines:
            param, _, value = line.partition(':')
            if param.strip().lower() == 'file':
                return int(value.strip())
        _logger.error(
            "Cannot found number of opened files. Command: %s\n"
            "Output:\n%s",
            command, output)
        raise OSError("Cannot found number of opened files")

    def disable_netprofm_service(self):
        # The Windows service netprofm ('Network List Service') is used for automatic collects and
        # stores properties of connected networks. During the collecting the service can restart
        # the network stack, which may cause problems known as 'WinRM timeout'.
        # Based on observations:
        #   - this issue occurred only when Mediaserver started;
        #   - if netprofm is disabled, some tests experience unstable network performance,
        #      resulting in numerous retransmissions and leading to SSL errors.
        # Therefore, we should stop the service strictly in case of extreme necessity.
        self.run('sc config netprofm start= disabled')
        # net stop used to stop the service with its dependant services.
        self.run('net stop netprofm /y')


class EmptyStdout(Exception):
    pass


# See: https://wutils.com/wmi/root/cimv2/win32_perfrawdata_perfproc_process/
class _ProcessCounter:

    def __init__(self, counter_engine: PerformanceCounterEngine, pid: int):
        self._counter_engine = counter_engine
        self._pid = pid

    def get_last(self) -> Mapping[str, Optional[str]]:
        [process] = self._counter_engine.request_filtered(
            'Win32_PerfRawData_PerfProc_Process',
            {'IDProcess': str(self._pid)})
        return process


class _DisksCounter:

    def __init__(self, counter_engine: PerformanceCounterEngine):
        self._counter_engine = counter_engine

    def get_all(self) -> Collection[Mapping[str, Optional[str]]]:
        # See: https://wutils.com/wmi/root/cimv2/win32_perfrawdata_perfdisk_physicaldisk/#percentdiskreadtime_properties
        # WMI has some problems with naming - all properties are counters indeed.
        try:
            result = self._counter_engine.request_unfiltered('Win32_PerfRawData_PerfDisk_PhysicalDisk')
        except WmiFault as e:
            _logger.error(f'Failed to get DisksCounter statistics: {e}')
            return []
        return [disk_data for disk_data in result if disk_data['Name'] != '_Total']
