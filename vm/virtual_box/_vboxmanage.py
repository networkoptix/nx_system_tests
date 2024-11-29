# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import getpass
import logging
import os
import re
import shutil
import subprocess
import time
from abc import ABCMeta
from abc import abstractmethod
from functools import lru_cache
from pathlib import Path
from pathlib import PurePath
from typing import Collection
from typing import Mapping
from typing import Sequence

from config import global_config
from directories.filelocker import try_lock_exclusively
from directories.filelocker import wait_until_locked
from vm.hypervisor import Hypervisor
from vm.virtual_box._hypervisor_exceptions import VirtualBoxError
from vm.virtual_box._hypervisor_exceptions import VirtualBoxVMNotReady
from vm.virtual_box._hypervisor_exceptions import virtual_box_error_cls
from vm.virtual_box.run_as_user import list_users
from vm.virtual_box.run_as_user import run_as_local_user


def vbox_default_dir():
    return get_virtual_box().vms_dir()


def vbox_manage_list(entity: str) -> Collection[Mapping[str, str]]:
    return get_virtual_box().vboxmanage().list(entity)


def vboxmanage_locked(args: Sequence[str]):
    return get_virtual_box().vboxmanage().run_locked(args)


def vboxmanage(args: Sequence[str]):
    return get_virtual_box().vboxmanage().run(args)


def vboxmanage_until_success(args: Sequence[str]):
    return get_virtual_box().vboxmanage().run_until_success(args)


@lru_cache(1)
def get_virtual_box() -> '_VirtualBox':
    user = get_vbox_user()
    if os.name == 'nt':
        vbox_env = _WindowsVirtualBox(user)
    else:
        vbox_env = _LinuxVirtualBox(user)
    vbox_env.prepare()
    return vbox_env


@lru_cache(1)
def get_vbox_user():
    return _user_pool.acquire()


class _VirtualBox(Hypervisor, metaclass=ABCMeta):

    def __init__(self, user: str):
        self._vbox_user = user
        self._original_user = getpass.getuser()
        vboxmanage_executable = self._find_vboxmanage()
        self._vboxmanage = _VBoxManage(self._vbox_user, vboxmanage_executable)
        self._check_vbox_user_settings()

    def get_base_snapshot_uri(self, os_name: str):
        url = global_config[os_name]
        if not url.strip():
            raise ValueError(
                f"Snapshot URL of {os_name!r} is empty in current config; "
                "it could be intentional: it means that this machine "
                "is not allowed to use this snapshot, "
                "e.g. to avoid downloading many gigabytes by mistake")
        return url

    def vbox_user(self):
        return self._vbox_user

    def vboxmanage(self) -> '_VBoxManage':
        return self._vboxmanage

    @lru_cache(1)
    def vms_dir(self) -> Path:
        [properties] = self._vboxmanage.list('systemproperties')
        return Path(properties['Default machine folder'])

    def prepare(self):
        self._terminate_user_vboxsvc()
        # Settings must be cleaned up before any VBoxManage calls.
        self._clean_up_vbox_settings()
        # Strictly speaking, extpack is not absolutely essential and it may be
        # checked later, but without it, VirtualBox becomes practically unusable.
        # Checking it later would also violate the fail-fast philosophy.
        self._check_vbox_extpack()
        # Getting VMs folder requires VBoxManage call.
        self._clean_up_vms_folder()

    @abstractmethod
    def fix_permissions(self, path: Path):
        pass

    @abstractmethod
    def _terminate_user_vboxsvc(self):
        pass

    @abstractmethod
    def _clean_up_vms_folder(self):
        pass

    @abstractmethod
    def _clean_up_vbox_settings(self):
        pass

    @abstractmethod
    def _find_vboxmanage(self) -> PurePath:
        pass

    @abstractmethod
    def _check_vbox_user_settings(self):
        pass

    def _check_vbox_extpack(self):
        # The first block always exist and contains "Extension Packs:" key.
        # The first extpack, if exists, appears in the same block.
        output = self._vboxmanage.run(['list', 'extpacks'])
        [first_line, rest] = output.split('\n', 1)
        extpacks_count = _parse_extpack_count_line(first_line)
        if extpacks_count == 0:
            raise RuntimeError("VirtualBox Extension Pack is not installed")
        extpacks = _list_output_parse(rest)
        # In reality, there's only one more extpack is available...
        for i, extpack in enumerate(extpacks):
            name = extpack[f'Pack no. {i}']
            if name == 'Oracle VM VirtualBox Extension Pack':
                break
        else:
            raise RuntimeError(
                "VirtualBox Extension Pack is not installed, "
                f"but other extension packs are installed: {extpacks}")
        if extpack['Usable'].strip() != 'true':  # Has a space at the end.
            raise RuntimeError(
                "VirtualBox Extension Pack is installed, "
                f"but unusable: {extpack['Why unusable']}")

    def _run_as_vbox_user(self, args: Sequence[str], ok_exit_codes=(0,)):
        result = run_as_local_user(self._vbox_user, args)
        if result.exit_code not in ok_exit_codes:
            raise RuntimeError(
                f"Command {result.command} failed with exit code {result.exit_code};"
                f"stdout={result.stdout} stderr={result.stderr}")


class _WindowsVirtualBox(_VirtualBox):

    def __init__(self, user: str):
        super().__init__(user)
        self._domain = os.environ['USERDOMAIN']
        self._vbox_config_folder = Path(fr'C:\Users\{self._vbox_user}\.VirtualBox')

    def fix_permissions(self, path: Path):
        _logger.debug("No need to fix permissions on Windows.")

    def _terminate_user_vboxsvc(self):
        _logger.debug("Terminating VBoxSVC for user %s", self._vbox_user)
        kill = [
            r'C:\Windows\System32\taskkill.exe',
            '/f',  # Forcefully terminate the process(es)
            '/t',  # Terminates the specified process and any child processes
            '/im', 'VBoxSVC.exe',  # Specifies the image name of the process to be terminated
            ]
        # Username of the process running under other user is not visible in
        # tasklist.exe or taskkill.exe. Run taskkill.exe under VirtualBox user.
        self._run_as_vbox_user(kill, ok_exit_codes=(0, 128, 255))

    def _clean_up_vms_folder(self):
        # If folder not found - rmdir exits with code 2. Code and error message
        # are indistinguishable from situations when executable not found,
        # for example command with wrong path to cmd.exe will return the exact
        # same error. To avoid handling wrong errors, check if directory exists
        # before deleting it.
        if not self.vms_dir().exists():
            _logger.debug("%s folder with VMs does not exist", self.vms_dir())
            return
        _logger.debug("Remove %s", self.vms_dir())
        self._run_as_vbox_user([
            r'C:\Windows\System32\cmd.exe', '/c', 'rmdir', '/s', '/q', str(self.vms_dir()),
            ])
        self._run_as_vbox_user([
            r'C:\Windows\System32\cmd.exe', '/c', 'mkdir', str(self.vms_dir())])

    def _clean_up_vbox_settings(self):
        vbox_settings = [
            str(self._vbox_config_folder / 'VirtualBox.xml'),
            str(self._vbox_config_folder / 'VirtualBox.xml-prev'),
            ]
        _logger.debug("Remove %s", vbox_settings)
        # If parent folder not found - del command exit with code 1.
        # The code is different from the one when executable is not found.
        self._run_as_vbox_user(
            [r'C:\Windows\System32\cmd.exe', '/c', 'del', '/q', *vbox_settings],
            ok_exit_codes=(0, 1))

    def _find_vboxmanage(self):
        try:
            parent = os.environ['VBOX_MSI_INSTALL_PATH']
        except KeyError:
            raise RuntimeError("No VirtualBox installation found")
        return PurePath(parent) / 'VBoxManage.exe'

    def _check_vbox_user_settings(self):
        vbox_user_home = self._get_vbox_user_home()
        errors_and_commands = []
        errors_and_commands.append(self._check_original_user_read_permissions(vbox_user_home))
        original_user_cache = Path('~/.cache').expanduser()
        errors_and_commands.append(self._check_vbox_user_read_permissions(original_user_cache))
        errors_and_commands.append(self._check_vbox_user_write_permissions(original_user_cache))
        if any(e for e, _ in errors_and_commands):
            errors = [e for e, _ in errors_and_commands]
            commands = [c for _, c in errors_and_commands]
            message = 'User misconfiguration:' + '\n'.join(errors)
            message += '\n\nPlease run following commands in cmd.exe with administrator privileges:\n\n'
            message += '\n'.join(commands) + '\n'
            raise RuntimeError(message)

    def _get_vbox_user_home(self):
        system_drive = os.environ['SYSTEMDRIVE']
        vbox_user_home = Path(f'{system_drive}/Users/{self._vbox_user}')
        if not vbox_user_home.exists():
            raise RuntimeError(
                f"User's home directory {vbox_user_home} does not exist. "
                "To create user profile and a home dir run a command in a cmd.exe:\n"
                f"runas /user:%USERDOMAIN%\\{self._vbox_user} /profile \"cmd.exe /c whoami\"")
        return vbox_user_home

    def _check_original_user_read_permissions(self, vbox_user_home):
        vbox_user_temp_file = vbox_user_home / 'temp.txt'
        try:
            vbox_user_temp_file.write_text('irrelevant')
            vbox_user_temp_file.read_text()
            list(vbox_user_temp_file.parent.iterdir())
        except PermissionError:
            ou = self._original_user
            error = (
                f"User {ou!r} must directly (not via Administrators group) "
                f"have a full access to a {vbox_user_home} folder.")
            command = f"icacls {vbox_user_home} /grant:r {ou}:(OI)(CI)F /T"
        else:
            error = ''
            command = ''
        return error, command

    def _check_vbox_user_read_permissions(self, original_user_cache: Path):
        original_user_temp_file = original_user_cache / 'temp.txt'
        original_user_temp_file.write_text('irrelevant')
        list_directory_result = run_as_local_user(self._vbox_user, [
            'cmd.exe', '/c', 'dir', str(original_user_temp_file.parent)])
        read_file_result = run_as_local_user(self._vbox_user, [
            'cmd.exe', '/c', 'type', str(original_user_temp_file)])
        read_results = [list_directory_result, read_file_result]
        if any(r.exit_code != 0 for r in read_results):
            cf = original_user_temp_file.parent
            vu = self._vbox_user
            error = f"User {vu!r} must have a read-only permissions for a {cf} folder"
            command = f"icacls {cf} /grant:r {vu}:(OI)(CI)RX /T"
        else:
            _logger.debug(
                "Read operations in %s from user %s succeeded",
                original_user_cache, self._vbox_user)
            error = ''
            command = ''
        return error, command

    def _check_vbox_user_write_permissions(self, original_user_cache: Path):
        original_user_temp_file = original_user_cache / 'temp.txt'
        original_user_temp_file.unlink(missing_ok=True)
        write_file_result = run_as_local_user(self._vbox_user, [
            'cmd.exe', '/c', f'echo a > {original_user_temp_file}'])
        if write_file_result.exit_code == 0:
            original_user_temp_file.unlink()
            cf = original_user_temp_file.parent
            vu = self._vbox_user
            error = f"User {vu!r} must have a read-only permissions for a {cf} folder"
            command = f"icacls {cf} /grant:r {vu}:(OI)(CI)RX /T"
        else:
            _logger.debug(
                "Write operations in %s from user %s denied",
                original_user_cache, self._vbox_user)
            error = ''
            command = ''
        return error, command


class _LinuxVirtualBox(_VirtualBox):

    def __init__(self, user: str):
        super().__init__(user)
        self._vbox_config_folder = Path(f'/home/{self._vbox_user}/.config/VirtualBox/')

    def fix_permissions(self, path: Path):
        # On Linux VirtualBox create all files and folders with ownership
        # of the same user, that was executing VirtualBox commands,
        # and without any group or other permissions.
        # Add -R and +X permissions to allow to execute stat on folder.
        # Otherwise, copy log commands running from original the user will
        # not work.
        self._run_as_vbox_user(['chmod', '-R', 'g+rwX,o+rX', str(path)])

    def _terminate_user_vboxsvc(self):
        _logger.debug("Terminating VBoxSVC for user %s", self._vbox_user)
        pkill = ['pkill', '-U', self._vbox_user, '-SIGTERM', 'VBoxSVC']
        try:
            # pkill returns 1 if no process is found.
            self._run_as_vbox_user(pkill, ok_exit_codes=(0, 1))
        except subprocess.TimeoutExpired as e:
            _logger.info(e)
            pkill = ['pkill', '-U', self._vbox_user, '-SIGKILL', 'VBoxSVC']
            # pkill returns 1 if no process is found.
            self._run_as_vbox_user(pkill, ok_exit_codes=(0, 1))

    def _clean_up_vms_folder(self):
        _logger.debug("Remove %s", self.vms_dir())
        self._run_as_vbox_user(['rm', '-rf', str(self.vms_dir())])
        # Make VMs dir, otherwise it would be created by VirtualBox
        # without group and other permissions.
        self._run_as_vbox_user(['mkdir', '-m', '775', '-p', str(self.vms_dir())])

    def _clean_up_vbox_settings(self):
        # Make config dir, otherwise it would be created by VirtualBox
        # without group and other permissions.
        self._run_as_vbox_user(['mkdir', '-m', '775', '-p', str(self._vbox_config_folder)])
        vbox_settings = [
            str(self._vbox_config_folder / 'VirtualBox.xml'),
            str(self._vbox_config_folder / 'VirtualBox.xml-prev'),
            ]
        _logger.debug("Remove %s", vbox_settings)
        self._run_as_vbox_user(['rm', '-f', *vbox_settings])

    def _find_vboxmanage(self):
        name = 'VBoxManage'
        if shutil.which(name) is None:
            raise RuntimeError("No VirtualBox installation found")
        return PurePath(name)  # Use relative path to avoid logs clogging

    def _check_vbox_user_settings(self):
        vbox_user_home = self._get_vbox_use_home()
        errors_and_commands = []
        errors_and_commands.append(self._check_original_user_read_permissions(vbox_user_home))
        errors_and_commands.append(
            self._check_vbox_user_read_permissions(Path('~/.cache').expanduser()))
        if any(e for e, _ in errors_and_commands):
            errors = [e for e, _ in errors_and_commands]
            commands = [c for _, c in errors_and_commands]
            message = 'User misconfiguration:' + '\n'.join(errors)
            message += '\n\nPlease run following commands:\n\n' + '\n'.join(commands) + '\n'
            raise RuntimeError(message)

    def _get_vbox_use_home(self):
        vbox_user_home = Path(f'/home/{self._vbox_user}')
        if not vbox_user_home.exists():
            raise RuntimeError(
                f"User's home directory {vbox_user_home} does not exist. "
                "To create user home dir run a command:\n"
                f"sudo usermod -m -d {vbox_user_home}")
        return vbox_user_home

    def _check_original_user_read_permissions(self, vbox_user_home):
        vbox_user_temp_file = vbox_user_home / 'temp.txt'
        self._run_as_vbox_user(['touch', str(vbox_user_temp_file)])
        try:
            vbox_user_temp_file.read_text()
            list(vbox_user_temp_file.parent.iterdir())
        except PermissionError:
            ou = self._original_user
            error = f'User {ou!r} must have a read permissions to a {vbox_user_home} folder'
            command = '\n'.join([
                f'sudo chmod -R g+rX {vbox_user_home}',
                f'sudo usermod -a -G $(id -gn {self._vbox_user}) {ou}'])
        else:
            error = ''
            command = ''
        finally:
            self._run_as_vbox_user(['rm', '-f', str(vbox_user_temp_file)])
        return error, command

    def _check_vbox_user_read_permissions(self, original_user_cache: Path):
        original_user_temp_file = original_user_cache / 'temp.txt'
        original_user_temp_file.write_text('irrelevant')
        list_directory_result = run_as_local_user(self._vbox_user, [
            'ls', str(original_user_temp_file.parent)])
        read_file_results = run_as_local_user(self._vbox_user, [
            'cat', str(original_user_temp_file)])
        if any(result.exit_code != 0 for result in [list_directory_result, read_file_results]):
            ouc = original_user_temp_file.parent
            error = f'User {self._vbox_user!r} must have a read permissions for a {ouc} folder'
            command = '\n'.join([
                f'sudo chmod o=+X {ouc.parent}',
                f'sudo chmod -R o=rX {ouc}',
                ])
        else:
            error = ''
            command = ''
            _logger.debug(
                "Read operations in %s from user %s succeeded",
                original_user_cache, self._vbox_user)
        return error, command


class _VBoxManage:

    def __init__(self, user: str, executable: PurePath):
        self._user = user
        self._executable = executable

    def list(self, entity: str) -> Collection[Mapping[str, str]]:
        if entity == 'hdds':
            raise Warning(
                'vboxmanage list hdds can be 1000+ entries long and its request could take'
                'more than 5 seconds. Please avoid using it')
        output = self.run_until_success(['list', entity])
        if not output:
            _logger.debug("VBoxManage list %s: no items returned", entity)
            return []
        return _list_output_parse(output)

    def run_until_success(self, args: Sequence[str]):
        max_attempts = 5
        for attempt in range(1, max_attempts + 1):
            try:
                return self.run(args)
            except VirtualBoxVMNotReady:
                delay = 0.25 * attempt
                _logger.warning("VirtualBoxVMNotReady is occurred after %s attempt", attempt)
                time.sleep(delay)
        else:
            raise RuntimeError(
                f"Command has failed {max_attempts} times with the VirtualBoxVMNotReady exception")

    def run_locked(self, args: Sequence[str]):
        with wait_until_locked(Path('~/.VBoxManage.lock').expanduser()):
            return self.run(args)

    def run(self, args: Sequence[str]):
        command = [str(self._executable), *args]
        _logger.info('VBoxManage as user %s: run %s', self._user, args)
        result = run_as_local_user(self._user, command)
        _logger.debug(
            "Exit status %s: %s\n"
            "=== stdout ===\n"
            "%s\n"
            "=== stderr ===\n"
            "%s",
            result.exit_code,
            result.command,
            result.stdout.decode(errors='backslashreplace'),
            result.stderr.decode(errors='backslashreplace'))
        if result.exit_code == 0:
            return result.stdout.decode('ascii').strip().replace('\r\n', '\n')
        stderr_decoded = result.stderr.decode('ascii')
        _logger.debug("VirtualBox Error:\n%s", stderr_decoded)
        prefix = f'{self._executable.name}: error: '
        if prefix not in stderr_decoded:
            _logger.debug("Can't find prefix '%s' in stderr:\n%s", prefix, stderr_decoded)
            raise VirtualBoxError(stderr_decoded)
        first_error_line = next(
            line
            for line in stderr_decoded.splitlines()
            if line.startswith(prefix))
        message = first_error_line[len(prefix):]
        if message == "The object is not ready":
            raise VirtualBoxVMNotReady("VBoxManage fails: {}".format(message))
        mo = re.search(r'Details: code (\w+)', stderr_decoded)
        if not mo:
            raise VirtualBoxError(message)
        code = mo.group(1)
        raise virtual_box_error_cls(code)(message, stderr_decoded)


def _parse_extpack_count_line(first_line):
    [name, raw_value] = _list_line_parse(first_line)
    result = int(raw_value)
    if name != 'Extension Packs':
        raise RuntimeError("The fist line must be Extension Packs")
    return result


def _list_output_parse(output):
    result = []
    for entry in output.split('\n\n'):
        properties = {}
        for line in entry.split('\n'):
            [name, value] = _list_line_parse(line)
            properties[name] = value
        result.append(properties)
    return result


def _list_line_parse(line):
    [name, value] = re.split(r':[ \t]*', line, 1)
    return name, value


class _UserPool:

    def __init__(self):
        self._root = Path('~/.cache/user-locks').expanduser()
        self._root.mkdir(exist_ok=True)
        self._existing_users = list_users()
        # Start from the last user to avoid collision with preferred users in configs.
        self._ft_users = [f'ft-{i}' for i in range(199, 99, -1)]
        preferred_user = os.getenv('PREFERRED_USER_NAME')
        if preferred_user is not None:
            self._ft_users.insert(0, preferred_user)
        self._lock = None

    def acquire(self) -> str:
        if not any(user in self._existing_users for user in self._ft_users):
            raise RuntimeError(
                "Dedicated user for VirtualBox does not exist. Please create local non-admin user "
                "with home directory with name from range ft-100 - ft-199")
        if self._lock is not None:
            raise RuntimeError("Process already has locked user")
        for user in self._ft_users:
            if user not in self._existing_users:
                continue
            lock_file = self._root / f'{user}.lock'
            lock_file.touch()
            lock = open(lock_file, mode='rb')
            if try_lock_exclusively(lock.fileno()):
                self._lock = lock
                _logger.info("User %s is locked for VBoxManage commands", user)
                return user
            lock.close()
        raise RuntimeError("Cannot find free FT user to run VBoxManage commands")


class _UserDoesNotExist(Exception):
    pass


_logger = logging.getLogger(__name__)
_user_pool = _UserPool()
