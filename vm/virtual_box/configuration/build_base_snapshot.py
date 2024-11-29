# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import os
import shlex
import subprocess
import sys
from abc import ABCMeta
from abc import abstractmethod
from collections.abc import Mapping
from collections.abc import Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Optional
from typing import cast
from xml.etree import ElementTree

from _internal.service_registry import default_prerequisite_store
from directories import get_ft_snapshots_cache_root
from directories.prerequisites import DefaultDistributionGroup
from os_access import OsAccess
from os_access import PosixAccess
from os_access import WindowsAccess
from os_access import copy_file
from os_access.ldap.server_installation import ActiveDirectoryInstallation
from os_access.ldap.server_installation import OpenLDAPInstallation
from vm.hypervisor import Vm
from vm.virtual_box import VBoxAccessSettings
from vm.virtual_box._vbox_manage_medium import vbox_manage_create_medium
from vm.virtual_box._vboxmanage import vboxmanage
from vm.virtual_box._vm import VBoxVMDisk
from vm.virtual_box._vm_configuration import VBoxConfigurationTemplate


def main(args: Sequence[str]):
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)7s %(name)s %(message).5000s")
    if os.getenv('DRY_RUN'):
        _logger.info("Dry Run: Would build base image args %s", args)
        return 0
    [build_os] = args
    _logger.info("Building base snapshot for %s", build_os)
    snapshot = get_snapshot(build_os)
    snapshot_uri = snapshot.build()
    DefaultDistributionGroup().share_file(snapshot_uri, str(get_ft_snapshots_cache_root()))


def get_snapshot(os_name: str):
    supported_os = {
        'ubuntu18': _VBoxUbuntuBaseSnapshot(
            'ubuntu18',
            # https://cloud-images.ubuntu.com/releases/bionic/release/ubuntu-18.04-server-cloudimg-amd64.img
            image_prerequisite_path='software/ubuntu-18.04-server-cloudimg-amd64.img',
            ),
        'ubuntu20': _VBoxUbuntuBaseSnapshot(
            'ubuntu20',
            # https://cloud-images.ubuntu.com/releases/focal/release/ubuntu-20.04-server-cloudimg-amd64.img
            image_prerequisite_path='software/ubuntu-20.04-server-cloudimg-amd64.img',
            ),
        'ubuntu22': _VBoxUbuntuBaseSnapshot(
            'ubuntu22',
            # https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img
            image_prerequisite_path='software/jammy-server-cloudimg-amd64.img',
            ),
        'ubuntu24': _VBoxUbuntu24BaseSnapshot(
            'ubuntu24',
            # https://cloud-images.ubuntu.com/releases/noble/release-20240725/ubuntu-24.04-server-cloudimg-amd64.img
            image_prerequisite_path='software/ubuntu-24.04-server-cloudimg-amd64.img',
            ),
        'openldap': _VBoxOpenLDAPBaseSnapshot(
            'openldap',
            # https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img
            image_prerequisite_path='software/jammy-server-cloudimg-amd64.img',
            ),
        'chrome': _VBoxChromeBaseSnapshot(
            'chrome',
            # https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img
            image_prerequisite_path='software/jammy-server-cloudimg-amd64.img',
            chrome_version='124.0.6367.91',
            ),
        'win10': _VBoxWindows10BaseSnapshot('win10'),
        'win2019': _VBoxWindows2019BaseSnapshot('win2019'),
        'win11': _VBoxWindows11BaseSnapshot('win11'),
        'active_directory': _VBoxActiveDirectoryBaseSnapshot('active_directory'),
        }
    try:
        return supported_os[os_name]
    except ValueError:
        raise RuntimeError(f"{os_name} is not supported.")


class _VBoxBaseSnapshot(VBoxConfigurationTemplate, metaclass=ABCMeta):

    def __init__(self, name, ram_mb: int, cpu_count: int, guest_ports):
        super().__init__(name, ram_mb, cpu_count, VBoxAccessSettings(guest_ports))
        self._store = default_prerequisite_store

    def build(self):
        with self._prepared() as vm_control:
            uri = vm_control.save_as_base_snapshot(self._name, self._metadata())
            print(f"Exposed as URL: {uri}")
        return uri

    def _metadata(self) -> Mapping[str, str]:
        return {}

    @abstractmethod
    def collect_prerequisites(self):
        pass

    @abstractmethod
    @contextmanager
    def _prepared(self):
        pass

    def _vbox_additions_path(self) -> Path:
        return self._store.fetch('software/VBoxGuestAdditions_7.0.20.iso')

    def _storage_attach(self, vm_control: Vm, ctl: str, device: int, port: int, storage_type: str, path: Path):
        vboxmanage([
            'storageattach', vm_control.name,
            '--storagectl', ctl,
            '--device', str(device),
            '--port', str(port),
            '--type', storage_type,
            '--medium', str(path),
            ])

    def _storage_attach_emptydrive(self, vm_control: Vm, ctl: str, device: int, port: int):
        vboxmanage([
            'storageattach', vm_control.name,
            '--storagectl', ctl,
            '--device', str(device),
            '--port', str(port),
            '--type', 'dvddrive',
            '--medium', 'emptydrive',
            ])


class _VBoxLinuxBaseSnapshot(_VBoxBaseSnapshot, metaclass=ABCMeta):
    _packages: list[str]

    def __init__(self, name, image_prerequisite_path: str):
        super().__init__(name, ram_mb=1024, cpu_count=1, guest_ports={'tcp': {1: 22}})
        self._image_prerequisite_path = image_prerequisite_path
        self._seed_path = Path(__file__).parent / f'{self._name}'

    @contextmanager
    def _prepared(self):
        image_path = self._store.fetch(self._image_prerequisite_path)
        with self._vm_registered(VBoxClonedImage(image_path, resize_gb=32)) as vm_control:
            os_access = self._prepare_vm_access(vm_control)
            self._purge_services(os_access)
            self._setup(os_access)
            os_access.compact()
            vm_control.shutdown()
            yield vm_control

    @abstractmethod
    def _setup(self, os_access: PosixAccess):
        pass

    def _prepare_vm_access(self, vm_control):
        self._cloud_init_setup(vm_control)
        vm_control.power_on()
        os_access = vm_control.get_os_access()
        os_access.wait_ready(timeout_sec=60)
        if not isinstance(os_access, PosixAccess):
            raise RuntimeError(f"Got {os_access!r} instead of PosixAccess")
        return os_access

    def _cloud_init_setup(self, vm_control):
        seed_iso = create_iso_image(self._seed_path, vm_control.dir() / 'seed_data.iso')
        self._add_controller(vm_control, 'IDE')
        self._storage_attach(vm_control, 'IDE', 0, 0, 'dvddrive', seed_iso)
        self._storage_attach(vm_control, 'IDE', 0, 1, 'dvddrive', self._vbox_additions_path())
        vm_control.power_on()
        try:
            vm_control.wait_off(timeout_sec=120)
        except TimeoutError:
            vm_control.power_off()
            raise

    def _purge_services(self, os_access: OsAccess):
        # Some packages must be removed and several services must be disabled entirely
        # to prevent any "dpkg is blocked by another process"-bound issues
        os_access.run(
            command=[
                'apt', 'purge', '-y',
                'unattended-upgrades',
                'update-manager-core',
                'snapd',
                'motd-news-config',
                'ubuntu-advantage-tools',
                ],
            )
        # This is a compilation list of all known services across several Ubuntu versions
        os_access.run(['systemctl', 'mask', 'apt-daily-upgrade.timer'])
        os_access.run(['systemctl', 'mask', 'apt-daily-upgrade.service'])
        os_access.run(['systemctl', 'mask', 'apt-daily.timer'])
        os_access.run(['systemctl', 'mask', 'apt-daily.service'])
        os_access.run(['systemctl', 'mask', 'ondemand.service'])
        os_access.run(['systemctl', 'mask', 'systemd-timesyncd.service'])
        os_access.run(['systemctl', 'mask', 'motd-news.service'])
        os_access.run(['systemctl', 'mask', 'fstrim.service'])
        os_access.run(['systemctl', 'mask', 'anacron.timer'])
        os_access.run(['systemctl', 'mask', 'anacron.service'])
        os_access.run(['systemctl', 'mask', 'dpkg-db-backup.service'])
        os_access.run(['systemctl', 'mask', 'dpkg-db-backup.timer'])
        os_access.run(['systemctl', 'mask', 'e2scrub_all.timer'])
        os_access.run(['systemctl', 'mask', 'e2scrub_all.service'])
        os_access.run(['systemctl', 'mask', 'logrotate.timer'])
        os_access.run(['systemctl', 'mask', 'logrotate.service'])
        os_access.run(['systemctl', 'mask', 'man-db.timer'])
        os_access.run(['systemctl', 'mask', 'man-db.service'])
        os_access.run(['systemctl', 'mask', 'systemd-tmpfiles-clean.timer'])
        os_access.run(['systemctl', 'mask', 'systemd-tmpfiles-clean.service'])

    def _install_packages(self, os_access: PosixAccess):
        packages_url = self._store.url(f'software/{self._name}.tar.gz')
        os_access.run(f'wget -q {shlex.quote(packages_url)} -O - | tar -xzv --directory=/', timeout_sec=600)
        os_access.shell.run(['apt', 'install', '-y', *self._packages], env={'DEBIAN_FRONTEND': 'noninteractive'}, timeout_sec=600)
        os_access.run(['update-grub'])

    def _install_vbox_additions(self, os_access: PosixAccess):
        os_access.run(['mkdir', '/tmp/vbox_additions'])
        os_access.run(['mount', '/dev/sr1', '/tmp/vbox_additions'])
        # Ubuntu cloud images has "vboxguest" kernel module by default
        # which causes VBoxLinuxAdditions.run to exit with code 2
        # So, there is a workaround with disabling this module before installation
        os_access.run(['rmmod', 'vboxguest'], check=False)
        os_access.shell.run(['/tmp/vbox_additions/VBoxLinuxAdditions.run'])

    def _add_controller(self, vm_control: Vm, controller: str):
        vboxmanage([
            'storagectl', vm_control.name,
            '--name', controller,
            '--add', controller.lower(),
            ])

    def _xml_stub(self):
        return Path(__file__).parent / 'ubuntu.vbox'


class _VBoxUbuntuBaseSnapshot(_VBoxLinuxBaseSnapshot):

    def __init__(self, name, image_prerequisite_path: str):
        super().__init__(name, image_prerequisite_path)
        self._packages = [
            *_common_packages,
            *_vms_tests_packages,
            *_nx_mediaserver_packages,
            *_nx_client_packages,
            'xvfb',  # for running client in headless mode
            'imagemagick',  # provides 'import' command, used to take screenshots by test
            'mesa-utils',  # provides glxinfo, used to check if GLX is working under xvfb
            ]

    def _setup(self, os_access: PosixAccess):
        self._install_packages(os_access)
        self._install_vbox_additions(os_access)

    def collect_prerequisites(self):
        # Internet should be available
        image_path = self._store.fetch(self._image_prerequisite_path)
        with self._vm_registered(VBoxClonedImage(image_path, resize_gb=32)) as vm_control:
            os_access = self._prepare_vm_access(vm_control)
            try:
                os_access.run(['apt', 'clean'])
                os_access.run(['apt', 'update'])
                os_access.shell.run(
                    args=['apt', 'install', '-y', '--download-only', *self._packages],
                    env={'DEBIAN_FRONTEND': 'noninteractive'},
                    timeout_sec=600)
                os_access.run([
                    'tar', '-czvf', '/tmp/apt_packages.tar.gz',
                    '/var/lib/apt/lists/',
                    '/var/cache/apt/archives/',
                    ])
                destination = Path(f'{self._name}.tar.gz')
                copy_file(os_access.path('/tmp/apt_packages.tar.gz'), destination)
                print(f"Now, manually upload {destination.absolute()} to prerequisites store")
            finally:
                vm_control.power_off()


class _VBoxUbuntu24BaseSnapshot(_VBoxUbuntuBaseSnapshot):

    def __init__(self, name, image_prerequisite_path: str):
        super().__init__(name, image_prerequisite_path)
        self._packages.remove('libasound2')
        self._packages.append('libasound2t64')


class _VBoxChromeBaseSnapshot(_VBoxLinuxBaseSnapshot):

    def __init__(self, name, image_prerequisite_path: str, chrome_version: str):
        super().__init__(name, image_prerequisite_path)
        self._chrome_version = chrome_version
        self._packages = [
            *_common_packages,
            'vlc', 'vlc-plugin-access-extra', 'xvfb',
            './google-chrome-stable_amd64.deb',
            ]

    def _setup(self, os_access: PosixAccess):
        # https://www.ubuntuupdates.org/package/google_chrome/stable/main/base/google-chrome-stable
        self._install_packages(os_access)
        self._install_vbox_additions(os_access)
        os_access.run(['rm', 'google-chrome-stable_amd64.deb'])
        # Patch VLC for running as root: https://unix.stackexchange.com/questions/125546/how-to-run-vlc-player-in-root
        os_access.run('sed -i "s/geteuid/getppid/" /usr/bin/vlc')
        # Disable Chrome updates
        os_access.run('echo repo_add_once=false > /etc/default/google-chrome')
        # https://googlechromelabs.github.io/chrome-for-testing/
        chromedriver_url = self._store.url(f'software/chrome-{self._chrome_version}/chromedriver-linux64.zip')
        os_access.run(f'wget -q {shlex.quote(chromedriver_url)} -O - | busybox unzip - -j -d /root/')
        os_access.run('chmod +x chromedriver')

    def collect_prerequisites(self):
        # Internet should be available
        image_path = self._store.fetch(self._image_prerequisite_path)
        with self._vm_registered(VBoxClonedImage(image_path, resize_gb=32)) as vm_control:
            os_access = self._prepare_vm_access(vm_control)
            try:
                chrome_deb_url = self._store.url(f'software/chrome-{self._chrome_version}/google-chrome-stable_amd64.deb')
                os_access.run(['wget', chrome_deb_url], timeout_sec=300)
                os_access.run(['apt', 'clean'])
                os_access.run(['apt', 'update'])
                os_access.shell.run(
                    args=['apt', 'install', '-y', '--download-only', *self._packages],
                    env={'DEBIAN_FRONTEND': 'noninteractive'},
                    timeout_sec=600)
                os_access.run([
                    'tar', '-czvf', '/tmp/apt_packages.tar.gz',
                    '/var/lib/apt/lists/',
                    '/var/cache/apt/archives/',
                    '/root/google-chrome-stable_amd64.deb',
                    ])
                destination = Path(f'{self._name}.tar.gz')
                copy_file(os_access.path('/tmp/apt_packages.tar.gz'), destination)
                print(f"Now, manually upload {destination.absolute()} to prerequisites store")
            finally:
                vm_control.power_off()


class _VBoxOpenLDAPBaseSnapshot(_VBoxLinuxBaseSnapshot):

    def __init__(self, name, image_prerequisite_path: str):
        super().__init__(name, image_prerequisite_path)
        self._packages = [*_common_packages, 'slapd', 'ldap-utils']

    def _setup(self, os_access: PosixAccess):
        openldap = OpenLDAPInstallation(os_access)
        password = debconf_escape(openldap.password())
        debconf_set_selections = (
            f'slapd slapd/internal/adminpw password {password}\n'
            f'slapd slapd/internal/generated_adminpw password {password}\n'
            f'slapd slapd/password2 password {password}\n'
            f'slapd slapd/password1 password {password}\n'
            'slapd slapd/dump_database_destdir string /var/backups/slapd-VERSION\n'
            f'slapd slapd/domain string {debconf_escape(openldap.domain())}\n'
            'slapd slapd/purge_database boolean true\n'
            'slapd slapd/move_old_database boolean true\n'
            'slapd slapd/no_configuration boolean false\n'
            'slapd slapd/dump_database select when needed\n'
            )
        os_access.run(['debconf-set-selections'], input=debconf_set_selections.encode())
        self._install_packages(os_access)
        self._install_vbox_additions(os_access)
        openldap = OpenLDAPInstallation(os_access)
        # In case of slapd package dpkg-reconfigure is needed to configure additional params,
        # because after 'apt install' not all params are prompted.
        # See: https://ubuntu.com/server/docs/service-ldap
        os_access.run(['dpkg-reconfigure', '-f', 'noninteractive', 'slapd'])
        openldap.make_initial_setup()

    def collect_prerequisites(self):
        # Internet should be available
        image_path = self._store.fetch(self._image_prerequisite_path)
        with self._vm_registered(VBoxClonedImage(image_path, resize_gb=32)) as vm_control:
            os_access = self._prepare_vm_access(vm_control)
            try:
                os_access.run(['apt', 'clean'])
                os_access.run(['apt', 'update'])
                os_access.shell.run(
                    args=['apt', 'install', '-y', '--download-only', *self._packages],
                    env={'DEBIAN_FRONTEND': 'noninteractive'},
                    timeout_sec=600)
                os_access.run([
                    'tar', '-czvf', '/tmp/apt_packages.tar.gz',
                    '/var/lib/apt/lists/',
                    '/var/cache/apt/archives/',
                    ])
                destination = Path(f'{self._name}.tar.gz')
                copy_file(os_access.path('/tmp/apt_packages.tar.gz'), destination)
                print(f"Now, manually upload {destination.absolute()} to prerequisites store")
            finally:
                vm_control.power_off()


def debconf_escape(s):
    r"""Escape strings for use in debconf-set-selections command.

    See: https://github.com/nabetaro/debconf-translation/blob/master/debconf-set-selections#L194

    >>> debconf_escape('test\n')
    'test\\\n'
    """
    return s.replace('\n', '\\\n')


class _VBoxWindowsBaseSnapshot(_VBoxBaseSnapshot, metaclass=ABCMeta):
    # If Autounattend.xml is not accepted and the OS shows UI,
    # access via VirtualBox RDP,
    # press Shift+F10 to open the console window,
    # cd to "X:\",
    # search for log files with "dir /S *.log".
    # Some logs are in UCS-2 encoding, use iconv on them.

    def __init__(self, name, guest_ports: dict):
        super().__init__(name, ram_mb=4096, cpu_count=4, guest_ports=guest_ports)
        self._windows_sdk_url = 'software/26100.1.240331-1435.ge_release_WindowsSDK.iso'
        self._stages_dir = Path(__file__).parent / self._name

    def _metadata(self) -> Mapping[str, str]:
        # Reverse order: (Auto)unattend.xml from a later stage wins.
        paths = sorted(self._stages_dir.glob('*/*.xml'), reverse=True)
        for path in paths:
            _logger.info("Search %s for password", path)
            tree = ElementTree.parse(path)
            ns = {'': 'urn:schemas-microsoft-com:unattend'}
            element = tree.find(namespaces=ns, path=(
                'settings[@pass="oobeSystem"]/'
                'component[@name="Microsoft-Windows-Shell-Setup"]/'
                'UserAccounts/'
                'AdministratorPassword/'
                'Value'))
            if element is not None:
                # Assume plain text. It can be in base64-encoded.
                _logger.info("Found password in %s", path)
                return {'password': element.text}
        raise RuntimeError("Cannot find unattend XML with AdministratorPassword")

    def collect_prerequisites(self):
        _logger.info("There is no prerequisites collection stage for %s", self._name)

    def _share_folder(self, vm_control: Vm, path: Path, name: str):
        vboxmanage([
            'sharedfolder', 'add', vm_control.name,
            '--name', name,
            '--hostpath', str(path.absolute()),
            '--readonly',
            ])

    def _run_stage(self, vm_control, stage_name: str, timeout_sec: int, additional_iso_path: Optional[Path] = None):
        _logger.info("Run stage %s", stage_name)
        output_iso = vm_control.dir() / f'{stage_name}.iso'
        directory = self._stages_dir / stage_name
        create_iso_image(directory, output_iso)
        self._storage_attach(vm_control, 'USB', 0, 0, 'dvddrive', output_iso)
        if additional_iso_path is not None:
            self._storage_attach(vm_control, 'SATA', 0, 1, 'dvddrive', additional_iso_path)
        else:
            self._storage_attach_emptydrive(vm_control, 'SATA', 0, 1)
        vm_control.power_on()
        vm_control.wait_off(timeout_sec)

    def _xml_stub(self):
        return Path(__file__).parent / 'win.vbox'


class _VBoxWindows10BaseSnapshot(_VBoxWindowsBaseSnapshot):

    def __init__(self, name):
        super().__init__(name, {})
        # From: https://software-download.microsoft.com/download/sg/17763.107.101029-1455.rs5_release_svc_refresh_CLIENT_LTSC_EVAL_x64FRE_en-us.iso
        self._windows_iso_prerequisite_path = 'software/17763.107.101029-1455.rs5_release_svc_refresh_CLIENT_LTSC_EVAL_x64FRE_en-us.iso'
        self._shared_folder_prerequisites = [
            # From: https://download.microsoft.com/download/7/1/0/7105C7FF-768E-4472-AFD5-F29108D1E383/NM34_x64.exe
            'software/NM34_x64.exe',
            # From https://download.sysinternals.com/files/SysinternalsSuite.zip
            'software/SysinternalsSuite.zip',
            # From https://ftp.icm.edu.pl/packages/qt/development_releases/prebuilt/llvmpipe/windows/opengl32sw-64-mesa_11_2_2-signed_sha256.7z
            # See: https://doc.qt.io/qt-6/qt-attribution-llvmpipe.html
            'software/opengl32sw.dll',
            # From https://get.videolan.org/vlc/3.0.20/win64/vlc-3.0.20-win64.msi
            'software/vlc-3.0.19-win64.msi',
            ]

    @contextmanager
    def _prepared(self):
        image_path = self._store.fetch(self._windows_iso_prerequisite_path)
        windows_sdk_path = self._store.fetch(self._windows_sdk_url)
        for prerequisite_url in self._shared_folder_prerequisites:
            self._store.fetch(prerequisite_url)
        with self._vm_registered(VBoxEmptyImage(size_gb=64)) as vm_control:
            self._share_folder(vm_control, image_path.parent, '.prerequisites')
            self._run_stage(vm_control, '10install', 900, image_path)
            self._run_stage(vm_control, '20additions', 300, self._vbox_additions_path())
            self._run_stage(vm_control, '40setup', 300, windows_sdk_path)
            self._run_stage(vm_control, '60oobe', 900)
            yield vm_control


class _VBoxWindows11BaseSnapshot(_VBoxWindowsBaseSnapshot):

    def __init__(self, name):
        super().__init__(name, {})
        # From: https://www.microsoft.com/en-us/evalcenter/download-windows-11-enterprise
        self._windows_iso_prerequisite_path = (
            'software/22631.2428.231001-0608.23H2_NI_RELEASE_SVC_REFRESH_CLIENTENTERPRISEEVAL_OEMRET_x64FRE_en-us.iso'
            )
        self._shared_folder_prerequisites = [
            # From: https://download.microsoft.com/download/7/1/0/7105C7FF-768E-4472-AFD5-F29108D1E383/NM34_x64.exe
            'software/NM34_x64.exe',
            # From https://download.sysinternals.com/files/SysinternalsSuite.zip
            'software/SysinternalsSuite.zip',
            # From https://ftp.icm.edu.pl/packages/qt/development_releases/prebuilt/llvmpipe/windows/opengl32sw-64-mesa_11_2_2-signed_sha256.7z
            # See: https://doc.qt.io/qt-6/qt-attribution-llvmpipe.html
            'software/opengl32sw.dll',
            # From https://get.videolan.org/vlc/3.0.20/win64/vlc-3.0.20-win64.msi
            'software/vlc-3.0.19-win64.msi',
            ]

    @contextmanager
    def _prepared(self):
        image_path = self._store.fetch(self._windows_iso_prerequisite_path)
        windows_sdk_path = self._store.fetch(self._windows_sdk_url)
        for prerequisite_url in self._shared_folder_prerequisites:
            self._store.fetch(prerequisite_url)
        with self._vm_registered(VBoxEmptyImage(size_gb=64)) as vm_control:
            self._share_folder(vm_control, image_path.parent, '.prerequisites')
            self._run_stage(vm_control, '10install', 900, image_path)
            self._run_stage(vm_control, '20additions', 120, self._vbox_additions_path())
            self._run_stage(vm_control, '40setup', 900, windows_sdk_path)
            self._run_stage(vm_control, '60oobe', 900)
            yield vm_control


class _VBoxWindows2019BaseSnapshot(_VBoxWindowsBaseSnapshot):

    def __init__(self, name):
        super().__init__(name, {})
        # From: https://software-download.microsoft.com/download/sg/17763.737.190906-2324.rs5_release_svc_refresh_SERVER_EVAL_x64FRE_en-us_1.iso
        self._windows_iso_prerequisite_path = 'software/17763.737.190906-2324.rs5_release_svc_refresh_SERVER_EVAL_x64FRE_en-us_1.iso'
        self._shared_folder_prerequisites = [
            # From: https://download.microsoft.com/download/7/1/0/7105C7FF-768E-4472-AFD5-F29108D1E383/NM34_x64.exe
            'software/NM34_x64.exe',
            # From https://download.sysinternals.com/files/SysinternalsSuite.zip
            'software/SysinternalsSuite.zip',
            ]

    @contextmanager
    def _prepared(self):
        image_path = self._store.fetch(self._windows_iso_prerequisite_path)
        windows_sdk_path = self._store.fetch(self._windows_sdk_url)
        for prerequisite_url in self._shared_folder_prerequisites:
            self._store.fetch(prerequisite_url)
        with self._vm_registered(VBoxEmptyImage(size_gb=64)) as vm_control:
            self._share_folder(vm_control, image_path.parent, '.prerequisites')
            self._run_stage(vm_control, '10install', 900, image_path)
            self._run_stage(vm_control, '20additions', 300, self._vbox_additions_path())
            self._run_stage(vm_control, '40setup', 300, windows_sdk_path)
            self._run_stage(vm_control, '50prepare', 300)
            self._run_stage(vm_control, '60oobe', 900)
            yield vm_control


class _VBoxActiveDirectoryBaseSnapshot(_VBoxWindowsBaseSnapshot):

    def __init__(self, name):
        super().__init__(name, guest_ports={'tcp': {1: 139, 2: 445, 4: 5985, 7: 389}})
        self._windows_iso_prerequisite_path = 'software/17763.737.190906-2324.rs5_release_svc_refresh_SERVER_EVAL_x64FRE_en-us_1.iso'
        self._shared_folder_prerequisites = [
            # From: https://download.microsoft.com/download/7/1/0/7105C7FF-768E-4472-AFD5-F29108D1E383/NM34_x64.exe
            'software/NM34_x64.exe',
            # From https://download.sysinternals.com/files/SysinternalsSuite.zip
            'software/SysinternalsSuite.zip',
            ]

    @contextmanager
    def _prepared(self):
        image_path = self._store.fetch(self._windows_iso_prerequisite_path)
        windows_sdk_path = self._store.fetch(self._windows_sdk_url)
        for prerequisite_url in self._shared_folder_prerequisites:
            self._store.fetch(prerequisite_url)
        with self._vm_registered(VBoxEmptyImage(size_gb=64)) as vm_control:
            self._share_folder(vm_control, image_path.parent, '.prerequisites')
            self._run_stage(vm_control, '10install', 900, image_path)
            self._run_stage(vm_control, '20additions', 300, self._vbox_additions_path())
            self._run_stage(vm_control, '40setup', 300, windows_sdk_path)
            self._run_stage(vm_control, '50prepare', 300)
            self._run_stage(vm_control, '60oobe', 900)
            self._run_stage(vm_control, '70ad', 900)
            self._run_stage(vm_control, '80password', 900)
            self._run_stage(vm_control, '90shutdown', 900)
            # Windows runs StartupRun.cmd from the attached USB drive after startup (which remains
            # from the last stage).
            self._storage_attach_emptydrive(vm_control, 'USB', 0, 0)
            vm_control.power_on()
            os_access = cast(WindowsAccess, vm_control.get_os_access())
            os_access.wait_ready(timeout_sec=300)
            ad_installation = ActiveDirectoryInstallation(os_access)
            ad_installation.wait_until_ready()
            ad_installation.make_initial_setup()
            vm_control.shutdown()
            yield vm_control


class VBoxClonedImage(VBoxVMDisk):

    def __init__(self, image_path: Path, resize_gb: int):
        self._image_path = image_path
        self._resize_gb = resize_gb

    def create(self, destination):
        vboxmanage([
            'clonemedium',
            'disk', str(self._image_path), str(destination),
            '--format', 'vdi',
            ])
        vboxmanage([
            'modifymedium', 'disk',
            str(destination),
            '--resizebyte', str(self._resize_gb * 1024 * 1024 * 1024),
            ])


class VBoxEmptyImage(VBoxVMDisk):

    def __init__(self, size_gb):
        self._size_gb = size_gb

    def create(self, destination):
        vbox_manage_create_medium(str(destination), self._size_gb * 1024)


def _nt_find_oscdimg():
    paths = [
        r'C:\Program Files (x86)\Windows Kits\10\Assessment and Deployment Kit\Deployment Tools\amd64\Oscdimg',
        r'~\.cache',
        ]
    for path in paths:
        oscdimg_path = Path(path).expanduser() / 'oscdimg.exe'
        if oscdimg_path.exists():
            return oscdimg_path.expanduser()
    else:
        raise FileNotFoundError(
            "Could not find oscdimg.exe\n"
            "Consider to download it from https://prerequisites.us.nxft.dev/software/oscdimg.exe"
            " and put it to any of the following directories:\n"
            + "\n".join(paths))


def create_iso_image(source_root: Path, target_file: Path):
    if os.name == 'nt':
        args = [
            # See: https://learn.microsoft.com/en-us/windows-hardware/manufacture/desktop/oscdimg-command-line-options?view=windows-11
            str(_nt_find_oscdimg()),
            '-lcidata',
            '-j1',
            '-o',
            '-m',
            str(source_root),
            str(target_file),
            ]
    else:
        args = [
            'genisoimage',
            '-output', str(target_file),
            '-volid', 'cidata',
            '-joliet',
            '-rock',
            '-input-charset', 'utf-8',
            str(source_root),
            ]
    timeout_sec = 5
    try:
        result = subprocess.run(args, capture_output=True, timeout=timeout_sec)
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"Command {args} did not finish in {timeout_sec:.1f} seconds")
    if result.returncode != 0:
        raise OSError((
            f"{result.args!r}\n"
            f"exit_code={result.returncode}\n"
            f"stdout: {result.stdout.decode().strip()}\n"
            f"stderr: {result.stderr.decode().strip()}"
            ))
    return target_file


_logger = logging.getLogger(__name__)
_common_packages = [
    # VBoxAdditions
    'bzip2', 'make', 'perl', 'gcc',
    # sfill for compacting image
    'secure-delete',
    # Network traffic between host and VM is captured with tshark.
    'tshark',
    ]
_vms_tests_packages = [
    # If mediaserver is hanging, memory dumps are taken with gcore.
    # Along with crash dumps, they are parsed with gdb.
    'gdb',
    # SMB server and client for SMB storage tests and SMB access self-tests.
    'smbclient', 'samba',
    # iSCSI server support
    'tgt',
    # Built-in "python -m zipfile -e" is not clear enough.
    'unzip',
    'zfsutils-linux',
    ]
_nx_mediaserver_packages = [
    # See (dev/nx): vms/distribution/deb/mediaserver/deb_dependencies.yaml
    "cifs-utils",
    "debconf",
    "file",
    "libcap2-bin",
    "libexpat1",
    "net-tools",
    "zlib1g",
    "libglib2.0-0",
    ]
_nx_client_packages = [
    # See (dev/nx): open/vms/distribution/deb/client/deb_dependencies.yaml
    "libegl1",
    "libfontconfig1",
    "libfreetype6",
    "libgl1",
    "libglu1-mesa",
    "libopengl0",
    "libpulse-mainloop-glib0",
    "libpulse0",
    "libsecret-1-0",
    "libx11-6",
    "libx11-xcb1",
    "libxcb-cursor0",
    "libxcb-glx0",
    "libxcb-icccm4",
    "libxcb-image0",
    "libxcb-keysyms1",
    "libxcb-randr0",
    "libxcb-render-util0",
    "libxcb-shape0",
    "libxcb-shm0",
    "libxcb-sync1",
    "libxcb-util1",
    "libxcb-xfixes0",
    "libxcb-xinerama0",
    "libxcb-xkb1",
    "libxext6",
    "libxfixes3",
    "libxkbcommon0",
    "libxss1",
    "zlib1g",
    "libasound2",
    "libglib2.0-0",
    "libdbus-1-3",
    "libexpat1",
    "libnspr4",
    "libnss3",
    "libxcomposite1",
    "libxdamage1",
    "libxi6",
    "libxkbfile1",
    "libxml2",
    "libxrandr2",
    "libxrender1",
    "libxslt1.1",
    "libxtst6",
    "debconf",
    ]


if __name__ == '__main__':
    exit(main(sys.argv[1:]))
