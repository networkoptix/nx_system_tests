# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import csv
import functools
import io
import json
import logging
import re
import shlex
import time
from configparser import ConfigParser
from contextlib import contextmanager
from contextlib import suppress
from datetime import datetime
from subprocess import CalledProcessError
from subprocess import TimeoutExpired
from typing import Mapping
from typing import Optional
from typing import Tuple

from os_access._exceptions import DeviceBusyError
from os_access._exceptions import ServiceFailedDuringStop
from os_access._exceptions import ServiceNotFoundError
from os_access._exceptions import ServiceUnstoppableError
from os_access._exceptions import UnknownExitStatus
from os_access._linux_networking import LinuxNetworking
from os_access._networking import Networking
from os_access._os_access_interface import Disk
from os_access._os_access_interface import DiskIoInfo
from os_access._os_access_interface import OsAccess
from os_access._os_access_interface import RamUsage
from os_access._path import RemotePath
from os_access._path import copy_file
from os_access._service_interface import Service
from os_access._service_interface import ServiceStartError
from os_access._service_interface import ServiceStatus
from os_access._sftp_path import SftpPath
from os_access._ssh_shell import Ssh
from os_access._ssh_shell import SshNotConnected
from os_access._ssh_traffic_capture import SSHTrafficCapture
from os_access._traffic_capture import TrafficCapture

_logger = logging.getLogger(__name__)


class _SystemdService(Service):
    """Control a Systemd service with `status`, `start` and `stop` shortcuts."""

    def __init__(self, shell: Ssh, name: str):
        self._shell = shell
        self._name = name

    def __repr__(self):
        return '<_SystemdService {} at {}>'.format(self._name, self._shell)

    @functools.lru_cache()
    def get_username(self):
        result = self._shell.run(['systemctl', 'show', '-pUser', self._name])
        _, user = result.stdout.decode('ascii').strip().split('=', 1)
        if not user:
            raise RuntimeError("Something went wrong. User is empty")
        return user

    def start(self, timeout_sec=None):
        if timeout_sec is None:
            timeout_sec = 10
        try:
            self._shell.run(['systemctl', 'start', self._name], timeout_sec=timeout_sec)
        except CalledProcessError as e:
            stdout = e.stdout.decode('ascii')
            stderr = e.stderr.decode('ascii')
            raise ServiceStartError(
                f"Service {self._name} failed to start with error code {e.returncode}:\n"
                f"stdout: {stdout}\n"
                f"stderr: {stderr}")

    def stop(self, timeout_sec=None):
        if timeout_sec is None:
            timeout_sec = 10
        _logger.info("Stop service %s.", self._name)
        try:
            self._shell.run(['systemctl', 'stop', self._name], timeout_sec=timeout_sec)
        except TimeoutExpired:
            status = self.status()
            if status.pid == 0:
                _logger.error("Timed out stopping %s; no process reported.", self._name)
            else:
                _logger.error("Timed out stopping %s; kill process %d.", self._name, status.pid)
                raise ServiceUnstoppableError(
                    f"Mediaserver is not stopping for {timeout_sec} seconds")
        result = self._shell.run(['systemctl', 'show', '-p', 'SubState', self._name])
        [_, sub_state] = result.stdout.decode('ascii').strip().split('=', 1)
        if sub_state == 'failed':
            raise ServiceFailedDuringStop(f"Error occurred while stopping {self._name}")

    def status(self):
        result = self._shell.run([
            'systemctl', 'show', '-p', 'SubState,MainPID,LoadState', self._name])
        data = dict(line.split('=', 1) for line in result.stdout.decode('ascii').splitlines())

        if data['LoadState'] == 'not-found':
            raise ServiceNotFoundError(f"Service {self._name!r} not found")

        return ServiceStatus(
            data['SubState'] == 'running',
            data['SubState'] in ['dead', 'failed'],
            int(data['MainPID']))

    def create(self, command):
        path = '/lib/systemd/system/{}.service'.format(self._name)
        script = shlex.join(command)
        config = (
            '[Unit]\n'
            'Description="FT-created service"\n'
            '\n'
            '[Service]\n'
            'ExecStart={script}\n'
            .format(script=script))
        self._shell.run(['tee', path], input=config.encode())
        self._shell.run(['systemctl', 'daemon-reload'])


class PosixAccess(OsAccess):
    OS_FAMILY = "linux"
    _iscsi_iqn_prefix = 'iqn.2020.01.nx.ft:'

    def __init__(
            self,
            address, port_map,
            shell: Ssh,
            traffic_capture: TrafficCapture,
            networking: Networking,
            ):
        super(PosixAccess, self).__init__(
            address, port_map,
            networking,
            )
        self._traffic_capture = traffic_capture
        self.shell = shell
        self._iscsi_connection_dir = self.path('/opt/iscsi')
        self._cpu_usage = _CPUUsageProvider(self)

    def __repr__(self):
        return f'<{self.__class__.__name__} {self.netloc()}>'

    @classmethod
    def to_vm(
            cls,
            ssh_user_name: str,
            ssh_private_key: str,
            address='127.0.0.1',
            port_map=None,
            ) -> 'PosixAccess':
        ssh_port = cls._get_port(port_map, 'tcp', 22)
        ssh = Ssh(address, ssh_port, ssh_user_name, ssh_private_key)
        traffic_capture = SSHTrafficCapture(ssh, SftpPath(ssh, '/root/ft/nx-traffic-capture'))
        return cls(
            address, port_map,
            ssh, traffic_capture,
            LinuxNetworking(ssh),
            )

    def netloc(self):
        return self.shell.netloc()

    def is_ready(self):
        """Ensure that OS is ready, including the iSCSI service.

        If the ISCSI daemon is present,
        it could become ready after the OpenSSH daemon.
        If things go too fast, we could start doing something before the end
        of the boot sequence, i.e. before all the services are up and running.
        If shutdown is performed at this moment, the VM may hang for minutes.
        """
        if self.shell.is_working():
            try:
                return self.service('tgt.service').is_running()
            except ServiceNotFoundError:
                _logger.debug("Shell is working but ISCSI server is not installed")
                return True
        return False

    @functools.lru_cache()
    def home(self, user=None) -> SftpPath:
        if user is None:
            user = self.user()
        try:
            run_result = self.shell.run(['getent', 'passwd', user])
        except CalledProcessError as e:
            if e.returncode != 2:
                raise
            raise RuntimeError(f"Can't determine home directory for {user !r}")
        raw = run_result.stdout.decode().split(':')[5]
        return self.path(raw)

    @functools.lru_cache()
    def user(self):
        return self.shell.run(['whoami']).stdout.decode().rstrip('\n')

    def tmp(self) -> SftpPath:
        return self.path('/tmp')

    def path(self, *parts) -> SftpPath:
        return SftpPath(self.shell, *parts)

    @property
    def traffic_capture(self):
        return self._traffic_capture

    def Popen(self, command):
        return self.shell.Popen(command)

    def run(
            self,
            command,
            input: Optional[bytes] = None,
            timeout_sec: float = 60,
            check=True,
            ):
        return self.shell.run(
            command,
            input=input,
            timeout_sec=timeout_sec,
            check=check,
            )

    def hostname(self):
        return self.run(['hostname']).stdout.strip().decode()

    def set_hostname(self, hostname):
        self.run(['hostnamectl', 'set-hostname', hostname])

    @functools.lru_cache()
    def _env_vars(self):
        output = self.run(['env']).stdout
        result = {}
        for line in output.decode('ascii').rstrip().splitlines():
            name, value = line.split('=', 1)
            result[name] = value
        return result

    def _clear_and_enable_logs(self):
        # Everything is already enabled.
        self.run(['dmesg', '--clear'])
        self.run(['journalctl', '--flush', '--rotate'])
        self.run(['journalctl', '--vacuum-time=0'])
        for file in self.path('/var/log/samba/').glob('log.*'):
            file.unlink()

    def download_system_logs(self, target_local_dir):
        prefix = self.netloc().replace(':', '-')
        dmesg_log = self.run(['dmesg', '-T']).stdout
        dmesg_path = target_local_dir / f'{prefix}-dmesg.log'
        dmesg_path.write_bytes(dmesg_log)
        journalctl_cmd = [
            'journalctl',
            '--output', 'short-precise',  # Include microseconds
            ]
        journalctl_log = self.run(journalctl_cmd).stdout
        journalctl_path = target_local_dir / f'{prefix}-journalctl.log'
        journalctl_path.write_bytes(journalctl_log)
        for file in self.path('/var/log/samba/').glob('log.*'):
            smb_log_file_name = 'smb_server-' + file.stem
            copy_file(file, target_local_dir / smb_log_file_name)

    def reboot(self):
        """Reboot and return when OS has been rebooted."""
        # Last reboot output is used as it, by definition, should change only if reboot occurred.
        self.traffic_capture.stop()
        last_reboot_before = self.run(['last', 'reboot']).stdout
        try:
            # Enough to call .Popen. Invoking with .run times out:
            # system goes to reboot before the command execution finishes.
            self.shell.Popen(['reboot'])
        except UnknownExitStatus:
            _logger.warning("Machine has already gone into reboot.")
        self.shell.close()
        _logger.info("Sleep while definitely rebooting.")
        time.sleep(3)
        started_at = time.monotonic()
        while time.monotonic() - started_at <= 30:
            try:
                last_reboot_after = self.run(['last', 'reboot']).stdout
            except SshNotConnected:
                _logger.debug("Still offline; reconnect in a while.")
                time.sleep(1)
            else:
                if last_reboot_after != last_reboot_before:
                    _logger.info("Rebooted.")
                    break
                self.shell.close()
                _logger.debug("Still online; sleep while OS is definitely rebooting.")
                time.sleep(3)
        else:
            raise RuntimeError("Can't reboot the machine")
        self.traffic_capture.start()

    def kill_all_by_name(self, executable_name):
        try:
            self.run(['killall', '-SIGKILL', executable_name])
        except CalledProcessError as e:
            if e.returncode != 1:
                raise

    def _pause_process(self, pid):
        self.run(['kill', '-STOP', pid])

    def _resume_process(self, pid):
        try:
            self.run(['kill', '-CONT', pid])
        except CalledProcessError as e:
            _logger.error(
                "The paused process has already been killed. "
                "This might be caused by the OOM killer. See dmesg.log",
                exc_info=e,
                )
            raise

    @contextmanager
    def process_paused(self, pid):
        self._pause_process(pid)
        try:
            yield
        except Exception:
            with suppress(CalledProcessError):
                self._resume_process(pid)
            raise
        self._resume_process(pid)

    def _mounted_fake_disks(self):
        mounts_file = self.path('/proc/self/mounts').read_text('utf8')
        result = []
        for line in mounts_file.splitlines():
            fs_spec, mount_point, fs_type, _, _, _ = line.split()
            # Conversion is just for consistency. Mount points, created here,
            # don't include spaces or backslashes. See: man fstab.
            mount_point.replace(r'\040', ' ').replace(r'\134', r'\\')
            if not fs_spec.startswith('/dev/loop'):
                _logger.debug("Skip, not a loop: %s", fs_spec)
                continue
            if not self.path(mount_point).parent != '/mnt':
                _logger.debug("Skip, not in /mnt: %s", fs_spec)
                continue
            result.append(self.path(mount_point))
        return result

    def is_fake_disk_mounted(self, letter):
        return letter in [path.name for path in self._mounted_fake_disks()]

    def fs_root(self) -> SftpPath:
        return self.path('/')

    def volumes(self):
        run_result = self.run([
            'df',
            '--output=target,size,avail',
            '--block-size=1',  # By default it's 1024 and all values are in kilobytes.
            ])
        result = {}
        for line in run_result.stdout.splitlines()[1:]:  # Mind header.
            target, size, avail = line.decode().split()
            result[self.path(target)] = Disk(int(size), int(avail))
        return result

    def create_file(self, file_path, file_size_b):
        self.run(['truncate', '-s', file_size_b, file_path])
        self.run(['fallocate', '-l', file_size_b, file_path])

    def get_datetime(self) -> datetime:
        started_at = time.monotonic()
        # --iso-8601 would also work, but it was deprecated for several years
        # and has a comma instead of a period before the nanoseconds.
        result = self.run(['date', '--rfc-3339=ns'], timeout_sec=2)
        delay_sec = time.monotonic() - started_at
        output = result.stdout.decode('ascii').rstrip()
        with_microseconds = re.sub(r'(\.\d{6})\d{3}', r'\1', output)
        local_time = datetime.fromisoformat(with_microseconds)
        _logger.debug("%r: Time %r, round trip %.3f sec", self, local_time, delay_sec)
        return local_time

    def set_datetime(self, new_time) -> None:
        started_at = time.monotonic()
        self.run(['date', '--set', new_time.isoformat(timespec='microseconds')])
        delay_sec = time.monotonic() - started_at
        _logger.debug(
            "%r: New time %r (our timezone), round trip %.3f sec",
            self, new_time, delay_sec)

    def _files_md5(self, paths):
        _logger.debug("Get MD5 of %d paths:\n%s", len(paths), '\n'.join(str(p) for p in paths))
        if not paths:
            return
        result = self.run(['md5sum', '--binary'] + paths, timeout_sec=300)
        for line in result.stdout.decode().splitlines():
            if not line:  # Last line is empty.
                continue
            if line[32:34] != ' *':  # `*` appears if file is treated as binary.
                raise RuntimeError(f"Malformed line in md5sum output: {line}")
            yield self.path(line[34:]), line[:32]
        for line in result.stderr.decode().splitlines():
            if not line or line.startswith('+'):  # Last empty line and tracing from set `-x`.
                continue
            if not line.endswith(': Is a directory'):
                raise RuntimeError('Cannot calculate MD5 on {}:\n{}'.format(self, result.stderr))

    def file_md5(self, file_path):
        (path, digest), = self._files_md5([file_path])
        return digest

    def folder_contents_size(self, folder):
        run_result = self.shell.run([
            'du',
            '--bytes',
            '--summarize',
            folder,
            ])
        [result, *_] = run_result.stdout.decode('ascii').split()
        return int(result)

    def files_size_sum(self, folder: SftpPath, extension: str) -> int:
        du_cmd = ['du', '--bytes', '--summarize', '--total']
        attempts = 0
        while True:
            attempts += 1
            try:
                output = self.run([
                    'find',
                    folder,
                    '-type', 'f',
                    '-name', f'*{extension}',
                    '-exec', *du_cmd, '{}', '+',
                    ])
            except CalledProcessError as exc:
                # Sometimes the error 'No such file or directory' appears when files are removed
                # from a directory during the execution.
                stderr = exc.stderr.decode(errors='backslashreplace')[:1000]
                if 'No such file or directory' not in stderr or not folder.exists() or attempts >= 3:
                    raise
            else:
                break
        if output.stdout == b'':
            return 0
        [*_, total_line] = output.stdout.strip().splitlines()
        [total_bytes, _] = total_line.split()
        return int(total_bytes)

    @functools.lru_cache()
    def source_address(self):
        env_vars = self._env_vars()
        var = env_vars['SSH_CONNECTION']
        return var.split(' ')[0]

    def service(self, name):
        return _SystemdService(self.shell, name)

    def dummy_service(self):
        service = self.service('func_tests_dummy')
        service.create(['/bin/sleep', '3600'])
        return service

    def close(self):
        # TODO: Close shell where it was created.
        self.shell.close()

    def dismount_fake_disk(self, mount_point):
        """Run "umount" on a file mounted as a block device.

        The lazy `umount` is used.
        From `man umount`:
        > Detach the filesystem from the file hierarchy now,
        > and clean up all references to this filesystem as soon as it is not
        busy anymore.

        The image file can be deleted even if it's still used.
        """
        self.shell.run(['fstab-decode', 'umount', '-l', mount_point])
        # File should be deleted too. Otherwise, it may contain data from previous test.
        image_path = mount_point.with_suffix('.img')
        try:
            image_path.unlink()
        except FileNotFoundError:
            pass

    def _form_mount_point(self, letter):
        return self.path('/mnt', letter.upper())

    def mount_fake_disk(self, letter, size_bytes):
        mount_point = self._form_mount_point(letter)
        image_path = mount_point.with_suffix('.img')
        # ext4 claims approximately 1,57% of disk size plus journal.
        # So make file bigger to make total space match size_bytes.
        claimed_by_fs = 0.0157
        # Journal size is relatively big for disks smaller than 1 Gb, for bigger disks
        # size error because of journal is small.
        # Journal size for 500 MB < disk_size < 2000 MB is 16 MB.
        journal_size_bytes = 16 * 1024**2
        disk_bytes = round(size_bytes / (1 - claimed_by_fs)) + journal_size_bytes
        self.shell.run(
            # language=Bash
            '''
                truncate --size=$SIZE "$IMAGE"
                mke2fs -t ext4 -F "$IMAGE"
                mkdir -p "$MOUNT_POINT"
                mount "$IMAGE" "$MOUNT_POINT"
                ''',
            env={
                'MOUNT_POINT': mount_point,
                'IMAGE': image_path,
                'SIZE': disk_bytes,
                })
        return mount_point

    def mount_smb_share(self, mount_point, path, username, password):
        self.path(mount_point).mkdir(parents=True, exist_ok=True)
        # umount times out by is 2x (v4.19) or 3x (f2caf901) echo_interval.
        # See: https://github.com/torvalds/linux/blob/master/fs/cifs/connect.c
        self.run([
            'mount', '-t', 'cifs', path, mount_point,
            '-o', f'user={username},password={password},vers=2.0,echo_interval=1'])

    def dismount_smb_share(self, mount_point, lazy=True):
        if lazy:
            self.run(['fstab-decode', 'umount', '-l', mount_point])
        else:
            try:
                self.run(['fstab-decode', 'umount', mount_point])
            except CalledProcessError as e:
                if e.returncode == 32:
                    raise DeviceBusyError("SMB share in use.")
                raise e

    def _get_block_devices(self):
        result = self.run([
            'lsblk',
            '--json',
            '--paths',  # Print full path.
            '--output', 'KNAME,PKNAME,MOUNTPOINT,TYPE',
            ])
        # Get rid of double backslashes in case of cyrillic characters.
        # There is a bug in lsblk: https://github.com/karelzak/util-linux/issues/330.
        # This bug is fixed in Ubuntu 18.04.
        result_decoded = result.stdout.decode('unicode-escape').encode('latin-1').decode()
        output_parsed = json.loads(result_decoded)
        return [device_data for device_data in output_parsed['blockdevices']]

    def _get_additional_disks(self):
        devices = self._get_block_devices()
        # ARM specified disks. Can't be unmounted. There are a lot of devices on ARMs.
        # /dev/zram0, /dev/zram1, /dev/mmcblk1boot1, /dev/mmcblk1boot2, etc.
        excluded_devices = ('/dev/mmcblk', '/dev/zram')
        [disk_with_system_partition] = [
            device['pkname']
            for device in devices
            if device['mountpoint'] == '/']
        return [
            device['kname']
            for device in devices
            if device['type'] == 'disk'
            if device['kname'] != disk_with_system_partition
            if not device['kname'].startswith(excluded_devices)
            ]

    def _list_disks_without_partition(self):
        block_devices = self._get_block_devices()
        disks = []
        disks_with_partition = []
        for device in block_devices:
            if device['type'] == 'disk':
                disks.append(device['kname'])
            elif device['type'] == 'part':
                disks_with_partition.append(device['pkname'])
        return [disk for disk in disks if disk not in disks_with_partition]

    def list_mounted_disks(self) -> Mapping[SftpPath, str]:
        devices = self._get_block_devices()
        result = {}
        for device in devices:
            if device['mountpoint'] is None:
                continue
            *_, name = device['pkname'].split('/')
            mountpoint = self.path(device['mountpoint'])
            result[mountpoint] = name
        return result

    def mount_disk(self, letter):
        new_disk = self._wait_for_newly_attached_disk_appears()
        mount_point = self._form_mount_point(letter)
        self._mount_fresh_disk(new_disk, mount_point)
        return mount_point

    @contextmanager
    def mount_disabled(self, mount_point):
        block_devices = self._get_block_devices()
        for device in block_devices:
            if device['mountpoint'] is None:
                continue
            if self.path(device['mountpoint']) == mount_point:
                partition = device['kname']
                break
        else:
            raise RuntimeError(f"Partition with mount {mount_point!r} not found")
        self.run(['fstab-decode', 'umount', '-l', partition])
        yield
        self.run(['mount', partition, mount_point])

    def _hosts_file(self):
        return self.path('/etc/hosts')

    def unzip(self, archive_path, dest_dir):
        # Man page does not mention long command line options.
        self.run([
            'unzip',
            '-o',  # -o is for "overwrite"; otherwise, it asks user
            archive_path,
            '-d', dest_dir,  # -d is for "destination"
            ])

    @functools.lru_cache()
    def arch(self):
        kernel_architecture = self.run(["uname", "-m"]).stdout.decode("ascii").strip()
        if kernel_architecture == 'armv7l':
            # Cortex-A72 powering Raspberry Pi 4 runs ELF32 executables on AArch32
            # (reported as 'armv7l') and ELF64 executables on AArch64
            return 'arm_32'
        elif kernel_architecture == 'aarch64':
            # Cortex-A76 powering Raspberry Pi 5 runs both ELF32 and ELF64 executables
            # on AArch64 (reported as 'aarch64') kernel
            output: str = self.run(['readelf', '-h', '/proc/1/exe']).stdout.decode('ascii')
            _logger.debug("Init process: %s", output)
            [_human_readable_header, *field_lines] = output.splitlines()
            elf_header_fields = {}
            for line in field_lines:
                key_raw, value_raw = line.strip().split(":", maxsplit=1)
                elf_header_fields[key_raw.strip()] = value_raw.strip()
            executable_format = elf_header_fields['Class']
            if executable_format == 'ELF32':
                return 'arm_32'
            elif executable_format == 'ELF64':
                return 'arm_64'
            raise RuntimeError(f"Unknown executable format {executable_format}")
        return kernel_architecture

    @functools.lru_cache()
    def _os_identification(self):
        with self.path('/etc/os-release').open(mode='r') as f:
            reader = csv.reader(f, delimiter='=')
            return {name: value for name, value in reader}

    @property
    def _samba_config_file(self):
        return self.path('/etc/samba/smb.conf')

    def _samba_config(self):
        config = ConfigParser()
        config_text = self._samba_config_file.read_text()
        config.read_string(config_text)
        return config

    def _write_samba_config(self, config):
        buffer = io.StringIO()
        config.write(buffer)
        self._samba_config_file.write_text(buffer.getvalue())

    @property
    def _samba_service(self):
        return _SystemdService(self.shell, 'smbd')

    def create_user(self, user, password, exist_ok=False):
        """Create a system and SMB user. Set a password for SMB only."""
        # TODO: Rename method to hint on SMB
        try:
            self.run(['useradd', user, '-c', self._user_description])
        except CalledProcessError as e:
            if exist_ok and e.returncode == 9 and b'already exists' in e.stdout + e.stderr:
                _logger.warning("User %s already exists. Password won't change", user)
            else:
                raise
        else:  # Don't change password if user already exists
            re_enter_password = (password.encode('ascii') + b'\n') * 2
            self.run(['smbpasswd', '-a', user], input=re_enter_password)

    def disable_user(self, name):
        raise RuntimeError("Disabling user in Linux is not implemented")

    def create_smb_share(self, name, path, user):
        if not path.is_absolute():
            raise ValueError("Absolute path must be specified.")

        config = self._samba_config()
        config['global']['log level'] = '3'  # Verbose
        config[name] = {
            'comment': 'FT test share',
            'path': str(path),
            'read only': 'no',
            'browsable': 'yes',
            }
        if user:
            config[name]['valid users'] = user
        else:
            config[name]['guest ok'] = 'yes'

        self._write_samba_config(config)

        self._samba_service.stop()
        self._samba_service.start()

    def _test_users(self):
        output_bytes = self.run(['cat', '/etc/passwd']).stdout
        test_users = []
        user_list = output_bytes.decode('utf-8').splitlines()
        for user in user_list:
            [name, _, _, _, description, _, _] = user.split(':')
            if description == self._user_description:
                test_users.append(name)
        return test_users

    def allow_access(self, path, user):
        self.run(['chown', '-R', user, str(path)])

    def allow_access_for_everyone(self, path):
        self.run(['chmod', '777', str(path)])

    def set_ssh_key_access(self, key_path):
        self.run(['chmod', '600', str(key_path)])

    @property
    def _iscsi_targets(self):
        result = self.run([
            'tgtadm', '--lld', 'iscsi', '--op', 'show', '--mode', 'target'])
        targets = {}
        for line in result.stdout.decode().splitlines():
            if line.startswith('Target'):
                [_, tid, iqn] = line.split()
                [_, name] = iqn.split(':')
                targets[name] = int(tid.rstrip(':'))
        return targets

    @property
    def _iscsi_target_dir(self):
        return self.path('/root/ft/iscsi')

    def create_iscsi_target(self, size, name):
        self._iscsi_target_dir.mkdir(parents=True, exist_ok=True)
        image = self._iscsi_target_dir / name
        if image.exists():
            image.unlink()
        self.create_file(image, size)
        target_iqn = self._iscsi_iqn_prefix + name
        target_ids = self._iscsi_targets.values()
        target_id = max(target_ids) + 1 if target_ids else 1
        self.run([
            'tgtadm',
            '--lld', 'iscsi',
            '--op', 'new',
            '--mode', 'target',
            '--tid', target_id,
            '--targetname', target_iqn,
            ])
        self.run([
            'tgtadm',
            '--lld', 'iscsi',
            '--op', 'new',
            '--mode', 'logicalunit',
            '--tid', target_id,
            '--lun', '1',
            '--backing-store', str(image),
            ])
        self.run([
            'tgtadm',
            '--lld', 'iscsi',
            '--op', 'bind',
            '--mode', 'target',
            '--tid', target_id,
            '--initiator-address', 'ALL',
            ])
        return target_iqn

    def _get_iscsi_disks_by_target(self) -> Mapping[str, RemotePath]:
        result = {}
        current_target = ""
        outcome = self.run([
            'iscsiadm',
            '--mode', 'session',
            '--print', '3',     # Verbosity of the output. Only level 3 print iSCSI LUNs
            ])
        sessions_output: str = outcome.stdout.decode('ascii')
        for line in sessions_output.splitlines():
            line = line.strip()
            if line.startswith("Target: "):
                [_, current_target, _] = line.split()
            elif line.startswith("Attached scsi disk "):
                [_, _, _, disk_name, *_] = line.split()
                disk_path = self.path("/dev") / disk_name
                _logger.info("Found iSCSI disk %s for target %s", disk_path, current_target)
                result[current_target] = disk_path
                current_target = ""
        if not result:
            _logger.info("None connected iSCSI disks were found")
        return result

    def _wait_iscsi_disk_connected(self, target_name: str) -> RemotePath:
        timeout_sec = 30
        end_at = time.monotonic() + timeout_sec
        while True:
            targets = self._get_iscsi_disks_by_target()
            target_path = targets.get(target_name)
            if target_path is not None:
                break
            if time.monotonic() > end_at:
                raise RuntimeError(f"iSCSI target {target_name} is not connected after {timeout_sec} sec")
            time.sleep(1)
        return target_path

    def _mount_fresh_disk(self, disk: RemotePath, mount_point: RemotePath):
        self.run(['fdisk', str(disk)], input=(
            b'o\n'  # Create DOS (MBR) partition table.
            b'n\n'  # New partition.
            b'\n'  # Default partition type - primary.
            b'\n'  # Default partition number - 1.
            b'\n'  # Default partition start - at the beginning of disk.
            b'\n'  # Default partition end - at the end of disk.
            b'w\n'  # Write changes.
            ))
        partition = str(disk) + '1'  # /dev/sdx -> /dev/sdx1
        _logger.debug("Format partition: %s", partition)
        self.run(['mkfs', '--type', 'ext4', partition])
        _logger.debug("Mount partition: %s -> %s", partition, mount_point)
        self.run(['mkdir', '-p', str(mount_point)])
        self.run(['mount', partition, str(mount_point)])
        return mount_point

    def _discover_iscsi_target(self, address: str, target_name: str):
        outcome = self.run([
            'iscsiadm',
            '--mode', 'discovery',
            '--type', 'st',  # Defines the discovery protocol. Use native iSCSI discovery protocol.
            '--portal', address,
            ])
        discovery_output: str = outcome.stdout.decode('ascii')
        server_targets = set()
        for line in discovery_output.splitlines():
            _, target = line.split()
            server_targets.add(target)
        if target_name not in server_targets:
            raise RuntimeError(
                f"Target {target_name} is not found in server "
                f"{address} amongst {server_targets}")

    def _log_in_to_iscsi_server(self, address: str, target_name: str):
        self.run([
            'iscsiadm',
            '--mode', 'node',
            '--targetname', target_name,
            '--portal', address,
            '--login',
            ])

    def mount_iscsi_disk(self, address, target_name):
        address = str(address)
        self._iscsi_connection_dir.mkdir(parents=True, exist_ok=True)
        # Target discovery must be performed first otherwise login will fail
        self._discover_iscsi_target(address, target_name)
        self._log_in_to_iscsi_server(address, target_name)
        iscsi_disk = self._wait_iscsi_disk_connected(target_name)
        _logger.info("%s is connected from %s:%s", iscsi_disk, address, target_name)
        self._mount_fresh_disk(iscsi_disk, self._iscsi_connection_dir)
        self.allow_access_for_everyone(self._iscsi_connection_dir)
        return self._iscsi_connection_dir

    def dismount_iscsi_disk(self, target_iqn):
        iscsi_disk = self._get_iscsi_disks_by_target()[target_iqn]
        self.run(['fstab-decode', 'umount', '--lazy', f'{iscsi_disk}1'])

    def _get_diagnostic_report(self):
        report = bytearray()
        self._run_diagnostic_command('date', 30, report)
        self._run_diagnostic_command('lsb_release -a', 30, report)
        self._run_diagnostic_command('free', 30, report)
        self._run_diagnostic_command('ip addr', 30, report)
        self._run_diagnostic_command('ip route', 30, report)
        self._run_diagnostic_command('arp -na', 30, report)
        self._run_diagnostic_command('iptables -L', 30, report)
        self._run_diagnostic_command('cat /etc/resolv.conf', 30, report)
        self._run_diagnostic_command('cat /etc/hosts', 30, report)
        self._run_diagnostic_command('ss -4nap', 30, report)
        self._run_diagnostic_command('mount', 30, report)
        self._run_diagnostic_command('df -h -x cifs', 30, report)  # Avoid inaccessible SMB mount
        self._run_diagnostic_command('du -aht 1M /mnt /root /opt | sort -h', 60, report)
        self._run_diagnostic_command('ps aux', 30, report)
        return bytes(report)

    def _run_diagnostic_command(self, command, timeout, report):
        output = self._handle_command_with_timeout(command, timeout)
        report.extend(command.encode(errors='backslashreplace') + b'\n\n' + output + b'\n')

    def get_cpu_name(self):
        cpu_info = self.path('/proc/cpuinfo').read_text('ascii')
        for line in cpu_info.splitlines():
            key, value = line.split(':')
            if key.strip() == 'model name':
                return value.strip()
        else:
            raise RuntimeError(f"CPU name not found in /proc/cpuinfo: {cpu_info}")

    def get_process_thread_count(self, pid):
        command = ['ps', '-eL', '-o', 'pid,nlwp', '--no-headers']
        processes = self.run(command).stdout.decode('ascii')
        for process in processes.splitlines():
            ps_pid, ps_thread_count = process.split()
            if pid == int(ps_pid):
                return int(ps_thread_count)
        else:
            raise RuntimeError(f"No process with {pid} found.")

    def get_ram_usage(self, pid):
        process_statm = self.path(f'/proc/{pid}/statm').read_text('ascii')
        process_status = self.path(f'/proc/{pid}/status').read_text('ascii')
        system_mem = self.path('/proc/meminfo').read_text('ascii')
        _, rss_pages, *_ = process_statm.split()
        rss_kbytes = int(rss_pages) * 4
        # Mem: total used free shared buff/cache available
        memory_stats = {}
        for stat in system_mem.splitlines():
            name, value, *_ = stat.split()
            memory_stats[name[:-1]] = int(value)  # name[:-1] to remove ':' from it.
        total_kbytes = memory_stats['MemTotal']
        process_usage = rss_kbytes / total_kbytes
        used_kbytes = total_kbytes - memory_stats['MemFree'] - memory_stats['Cached']
        total_usage = used_kbytes / total_kbytes
        match = re.search(r"^VmHWM:.*?(\d+)", process_status, flags=re.MULTILINE)
        if match is None:
            raise RuntimeError(f"Can't parse file /proc/{pid}/status")
        process_usage_peak_bytes = int(match.group(1)) * 1024
        return RamUsage(
            process_usage,
            total_usage,
            rss_kbytes * 1024,
            used_kbytes * 1024,
            process_usage_peak_bytes,
            )

    def _get_used_memory_mbytes(self):
        # Mediaserver's used memory count is different from what linux counts as used.
        # 'free' shows used RAM without extra calculations and is used to check that RAM
        # consuming process is working.
        result = self.run(['free', '-m'])
        mem = result.stdout.splitlines()[1]
        used_mbytes = mem.split()[2]
        return int(used_mbytes)

    def _start_ram_load(self, ram_mbytes):
        command = [
            'timeout', '-s', 'SIGKILL', '120s',
            'dd', f'bs={ram_mbytes}M', 'if=/dev/zero', 'of=/dev/null']
        self.shell.Popen(command)

    def stop_ram_load(self):
        self.kill_all_by_name('dd')

    def create_zfs_pool(
            self,
            pool_name: str,
            disk_count: int,
            mirrored: bool = False,
            ):
        started_at = time.monotonic()
        timeout_sec = 120
        while True:
            disks_without_partition = self._list_disks_without_partition()
            if len(disks_without_partition) == disk_count:
                break
            if time.monotonic() - started_at > timeout_sec:
                raise RuntimeError(
                    f"Found {len(disks_without_partition)} disks without partition "
                    f"after {timeout_sec} seconds, need exactly {disk_count}.")
        self.run([
            'zpool',
            'create',
            '-f',  # Force pool creation
            pool_name,
            *(['mirror'] if mirrored else []),
            *disks_without_partition,
            ])
        status_run = self.run([
            'zpool',
            'status',
            '-x',  # Only display status for pools that are exhibiting errors
            ])
        status_output = status_run.stdout.decode('ascii')
        if status_output.rstrip() != 'all pools are healthy':
            raise RuntimeError(f"ZFS pool improperly created, output: {status_output!r}")

    def list_total_cpu_usage(self, sample_interval_sec, sample_count):
        collect_cpu_usage_script = (
            'for (( i = 0; i <= $sample_count; i++ )); '
            'do '
            'head -n 1 /proc/stat; '
            'sleep $sample_interval_sec; '
            'done'
            )
        script_variables = {
            'sample_count': sample_count,
            'sample_interval_sec': sample_interval_sec,
            }
        additional_timeout = 5
        outcome = self.shell.run(
            collect_cpu_usage_script,
            env=script_variables,
            timeout_sec=(sample_count + 1) * sample_interval_sec + additional_timeout,
            )
        script_output = outcome.stdout.decode('ascii')
        uptime_samples = []
        for stat_line in script_output.splitlines():
            if not stat_line:
                continue
            stats = [int(stat) for stat in stat_line.split()[1:]]
            [idle, iowait] = stats[3:5]
            uptime_samples.append([sum(stats), idle + iowait])
        result = []
        for [old_uptime_content, new_uptime_content] in zip(uptime_samples, uptime_samples[1:]):
            [total, idle] = new_uptime_content
            [previous_total, previous_idle] = old_uptime_content
            result.append(1 - (idle - previous_idle) / (total - previous_total))
        return result

    def list_process_cpu_usage(self, pid, sample_interval_sec, sample_count):
        collect_cpu_usage_script = (
            'for (( i = 0; i <= $sample_count; i++ )); '
            'do '
            'cat /proc/$pid/stat; '
            'head -n 1 /proc/stat; '
            'sleep $sample_interval_sec; '
            'done'
            )
        script_variables = {
            'sample_count': sample_count,
            'pid': pid,
            'sample_interval_sec': sample_interval_sec,
            }
        additional_timeout = 5
        outcome = self.shell.run(
            collect_cpu_usage_script,
            env=script_variables,
            timeout_sec=(sample_count + 1) * sample_interval_sec + additional_timeout,
            )
        script_output = outcome.stdout.decode('ascii')
        process_stat_samples = []
        lines = [line for line in script_output.splitlines() if line]
        for [process_line, total_line] in zip(lines[::2], lines[1::2]):
            # We need process utime, stime, cutime, cstime.
            # utime - time the process spent in user mode.
            # stime - time the process spent in kernel mode.
            # cutime - time the process waited for children to be scheduled in user mode.
            # cstime - time the process waited for children to be scheduled in kernel mode.
            # See 'man proc' for more info.
            parameters = process_line.split()
            [user_mode_time, kernel_mode_time] = parameters[13:15]
            [children_user_mode_time, children_kernel_mode_time] = parameters[15:17]
            process_run_time = sum([
                int(user_mode_time),
                int(kernel_mode_time),
                int(children_user_mode_time),
                int(children_kernel_mode_time),
                ])
            total_time = sum(float(x) for x in total_line.split()[1:])
            process_stat_samples.append((process_run_time, total_time))
        result = []
        process_stat_pairs = zip(process_stat_samples, process_stat_samples[1:])
        for [previous, current] in process_stat_pairs:
            [previous_process_time, previous_total_time] = previous
            [process_time, total_time] = current
            process_time_spent = process_time - previous_process_time
            total = total_time - previous_total_time
            result.append(process_time_spent / total)
        return result

    def _start_cpu_load(self):
        self.shell.Popen(['sha1sum', '/dev/zero'])

    def _stop_cpu_load(self):
        self.kill_all_by_name('sha1sum')

    def _clean_apt_cache(self):
        self.shell.run(['apt', 'clean'])

    def compact(self):
        start_at = time.monotonic()
        logging.info("Compacting the image ...")
        self._clean_apt_cache()
        self._clear_and_enable_logs()
        command = [
            # See: https://www.unix.com/man-page/debian/1/SFILL/
            'sfill',
            '-v',  # Verbose mode.
            '-f',  # Fast and insecure: no /dev/urandom, no synchronize mode.
            '-l',  # Lessens security. Two passes: 0xff and random.
            '-l',  # Second time. Even less security. One pass with random.
            '-z',  # Wipes the last write with zeros instead of random data.
            '/',
            ]
        self.shell.run(command, timeout_sec=300)
        duration = time.monotonic() - start_at
        logging.info("Compacting took %s sec", duration)

    def add_trusted_certificate(self, cert_path):
        trusted_certs_dir = self.path('/usr/local/share/ca-certificates')
        # Certificate MUST have a '.crt' suffix otherwise it won't be processed
        # See: https://ubuntu.com/server/docs/security-trust-store
        cert_name = cert_path.stem + '.crt' if cert_path.suffix == '.pem' else cert_path.name
        copy_file(cert_path, trusted_certs_dir / cert_name)
        self.run(['update-ca-certificates'])

    def get_cpu_usage(self) -> float:
        return self._cpu_usage.get_current()

    @functools.lru_cache(1)
    def _get_system_parameter_clk_tck(self) -> int:
        outcome = self.shell.run('getconf CLK_TCK')
        script_output = outcome.stdout.decode('ascii')
        return int(script_output.strip())

    def get_cpu_time_process(self, pid: int):
        stat_file = self.path(f'/proc/{pid}/stat').read_text()
        stats = stat_file.split()
        [user_mode_time, kernel_mode_time] = stats[13:15]
        [children_user_mode_time, children_kernel_mode_time] = stats[15:17]
        process_run_time = sum([
            int(user_mode_time),
            int(kernel_mode_time),
            int(children_user_mode_time),
            int(children_kernel_mode_time),
            ])
        return process_run_time / self._get_system_parameter_clk_tck()

    def get_io_time(self):
        # See: https://www.kernel.org/doc/Documentation/ABI/testing/procfs-diskstats
        diskstats = self.path('/proc/diskstats').read_text()
        template = (
            r' +\d+ +\d+ (?P<device>sd[a-z])'
            r' (?P<r_completed>\d+) (?P<r_merged>\d+) (?P<sectors_r>\d+) (?P<time_spent_r>\d+)'
            r' (?P<w_completed>\d+) (?P<w_merged>\d+) (?P<sectors_w>\d+) (?P<time_spent_w>\d+)'
            r' .*'
            )
        pattern = re.compile(template)
        result = []
        for match in pattern.finditer(diskstats):
            disk_name = match.group('device')
            s = self.path(f'/sys/block/{disk_name}/queue/hw_sector_size').read_text()
            sector_size = int(s.strip())
            io_info = DiskIoInfo(
                name=disk_name,
                reading_sec=float(match.group('time_spent_r')) / 1000,
                writing_sec=float(match.group('time_spent_w')) / 1000,
                read_bytes=int(match.group('sectors_r')) * sector_size,
                write_bytes=int(match.group('sectors_w')) * sector_size,
                read_count=int(match.group('r_completed')),
                write_count=int(match.group('w_completed')),
                )
            result.append(io_info)
        return result

    def get_open_files_count(self, pid):
        command = f'lsof -p {pid} | wc -l'
        output = self.run(command).stdout.decode().strip()
        try:
            return int(output)
        except ValueError:
            pass
        _logger.error(
            "Cannot found number of opened files."
            "Command: %s\nOutput:\n%s",
            command, output)
        raise OSError("Cannot found number of opened files")

    def get_pid_by_name(self, executable_name: str) -> int:
        command = ['ps', '--no-headers', '-o', 'pid', '-C', executable_name]
        output = self.run(command, check=False).stdout.decode().strip().split()
        if not output:
            raise FileNotFoundError(f"Cannot found pid by name {executable_name!r}")
        if len(output) > 1:
            _logger.warning(
                "More than one pid {} found for name '%s'", output, executable_name)
        try:
            return int(output[0].strip())
        except ValueError:
            pass
        _logger.error(
            "Cannot found pid by name.\n"
            "Command: %s\nOutput:\n%s",
            command, output)
        raise FileNotFoundError(f"Cannot found pid by name {executable_name!r}")


class _CPUUsageProvider:

    def __init__(self, os_access: PosixAccess):
        self._os_access = os_access
        self._prev_used_time = 0
        self._prev_idle_time = 0

    def get_current(self) -> float:
        [current_used_time, current_idle_time] = self._get_current_processor_time()
        used_time = current_used_time - self._prev_used_time
        idle_time = current_idle_time - self._prev_idle_time
        self._prev_used_time, self._prev_idle_time = current_used_time, current_idle_time
        return used_time / (used_time + idle_time)

    def _get_current_processor_time(self) -> Tuple[float, float]:
        # Structure of /proc/stat:
        # cpu user nice system idle iowait irq softirq steal guest guest_nice
        # See: https://www.kernel.org/doc/Documentation/filesystems/proc.txt
        # See: https://stackoverflow.com/a/23376195
        stat_file = self._os_access.path('/proc/stat').read_text()
        [_, user, nice, system, idle, iowait, irq, softirq, steal, *_] = stat_file.split()
        used_time = sum([
            float(user),
            float(nice),
            float(system),
            float(irq),
            float(softirq),
            float(steal),
            ])
        idle_time = sum([
            float(idle),
            float(iowait),
            ])
        return used_time, idle_time
