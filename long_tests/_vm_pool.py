# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time
from contextlib import AbstractContextManager
from contextlib import ExitStack
from contextlib import contextmanager
from pathlib import Path
from typing import Collection
from typing import cast

from ca import default_ca
from distrib import InstallerNotFound
from gui.desktop_ui.main_window import MainWindow
from gui.desktop_ui.resource_tree import CurrentUserNodeNotFound
from gui.desktop_ui.resource_tree import ResourceTree
from gui.testkit import TestKit
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from installation import Mediaserver
from installation import VmsBenchmarkInstallation
from installation import WindowsClientInstallation
from installation import connect_from_command_line
from installation import find_mediaserver_installation
from mediaserver_api import MediaserverApiV2
from mediaserver_api import MediaserverApiV4
from mediaserver_scenarios.provisioned_mediaservers import OneMediaserverStand
from os_access import OsAccess
from os_access import PosixAccess
from os_access import WindowsAccess
from vm.client_vm_pool import vm_types as client_vm_types
from vm.default_vm_pool import public_default_vm_pool
from vm.default_vm_pool import vm_types
from vm.nxwitness_snapshots.client_plugin import ClientPlugin
from vm.nxwitness_snapshots.mediaserver_plugin import MediaserverPlugin
from vm.virtual_box._vm_configuration import VBoxSnapshotTemplate
from vm.vm import VM
from vm.vm_type import VMSnapshotTemplate


class VMPool:
    def __init__(
            self,
            artifact_dir: Path,
            installers_url: str,
            ):
        self._artifacts_dir = artifact_dir
        self._installers_url = installers_url
        self._vm_pool = public_default_vm_pool(self._artifacts_dir)
        default_ca().add_to_env_vars()

    @contextmanager
    def mediaserver_stand(
            self,
            vm_type: VMSnapshotTemplate,
            plugins: Collection[str] = None,
            full_logs: bool = False,
            ) -> AbstractContextManager[OneMediaserverStand]:
        installer_supplier = _find_installer_supplier(self._installers_url, vm_type.name())
        mediaserver_plugin = MediaserverPlugin(installer_supplier)
        # In Mediaserver 6.1, some breaking changes were made. It is better to use APIv4.
        if installer_supplier.distrib().older_than('vms_6.1'):
            api_class = MediaserverApiV2
        else:
            api_class = MediaserverApiV4
        with ExitStack() as stack:
            vm = stack.enter_context(self._vm_pool.vm_created(mediaserver_plugin, vm_type))
            try:
                vm.ensure_started(self._artifacts_dir)
                if isinstance(vm.os_access, PosixAccess):
                    vm.os_access.run(['ulimit', '-n', '4096'])
                stack.enter_context(vm.os_access.prepared_one_shot_vm(self._artifacts_dir))
                mediaserver = stack.enter_context(self._prepared_mediaserver(vm, api_class, full_logs))
                if plugins is not None:
                    mediaserver.enable_optional_plugins(plugins)
                mediaserver.start()
                mediaserver.api.setup_local_system()
                mediaserver.api.set_system_settings({
                    'autoDiscoveryEnabled': 'False',
                    'updateNotificationsEnabled': False,
                    })
                yield OneMediaserverStand(vm, mediaserver)
            except Exception:
                _logger.exception("An exception happened in mediaserver_stand():")
                vm.vm_control.take_screenshot(self._artifacts_dir / 'vm_exception.png')
                raise
            finally:
                vm.vm_control.copy_logs(self._artifacts_dir)

    @contextmanager
    def _prepared_mediaserver(
            self,
            vm: VM,
            api_class: type[MediaserverApiV2 | MediaserverApiV4],
            full_logs: bool,
            ) -> AbstractContextManager[Mediaserver]:
        mediaserver = find_mediaserver_installation(vm.os_access)
        with ExitStack() as exit_stack:
            try:
                exit_stack.callback(mediaserver.collect_artifacts, self._artifacts_dir)
                exit_stack.callback(mediaserver.check_for_error_logs)
                exit_stack.callback(mediaserver.stop, already_stopped_ok=True)
                mediaserver.stop()
                mediaserver.init_key_pair(default_ca().generate_key_and_cert(vm.os_access.address))
                mediaserver.init_api(api_class(mediaserver.base_url()))
                mediaserver.remove_data_from_previous_runs()
                mediaserver.enable_saving_console_output()
                if not full_logs:
                    mediaserver.remove_logging_ini()
                    mediaserver.set_main_log_level('Info')
                mediaserver.update_ini('nx_utils', {'assertCrash': 1, 'assertHeavyCondition': 1})
                mediaserver.update_conf({'maxConnections': 4000})
                yield mediaserver
            except Exception:
                mediaserver.take_backtrace('after_test')
                raise

    @contextmanager
    def benchmark_stand(self) -> AbstractContextManager['BenchmarkStand']:
        installer_supplier = _find_installer_supplier(self._installers_url, 'ubuntu22')
        mediaserver_plugin = MediaserverPlugin(installer_supplier)
        with ExitStack() as stack:
            vm = stack.enter_context(self._vm_pool.vm_created(mediaserver_plugin, vm_types['ubuntu22']))
            vm.ensure_started(self._artifacts_dir)
            # Mediaserver VM snapshot is in use, but running Mediaserver is not needed.
            vm.os_access.run(['systemctl', 'stop', 'networkoptix-mediaserver.service'], check=False)
            vm.os_access.run(['ulimit', '-n', '4096'])
            installer = installer_supplier.upload_benchmark(vm.os_access)
            benchmark = VmsBenchmarkInstallation(vm.os_access)
            benchmark.install(installer)
            if not benchmark.is_valid():
                raise RuntimeError(
                    f"Benchmark {installer_supplier} on {vm.os_access} "
                    f"is invalid when just installed")
            yield BenchmarkStand(vm, benchmark)

    @contextmanager
    def client_stand(self) -> AbstractContextManager['ClientStand']:
        installer_supplier = _find_installer_supplier(self._installers_url, 'win11')
        client_plugin = ClientPlugin(installer_supplier)
        with ExitStack() as stack:
            vm = stack.enter_context(self._vm_pool.vm_created(client_plugin, client_vm_types['win11']))
            stack.callback(vm.vm_control.copy_logs, self._artifacts_dir)
            try:
                vm.ensure_started(self._artifacts_dir)
                stack.enter_context(vm.os_access.prepared_one_shot_vm(self._artifacts_dir))
                client_installation = WindowsClientInstallation(
                    cast(WindowsAccess, vm.os_access),
                    installer_supplier.distrib().customization(),
                    installer_supplier.distrib().version(),
                    )
                client_installation.configure_for_tests()
                # Desktop Clients earlier than version 6.0 are not aware of opengl32sw.dll
                # and expect opengl32.dll
                if client_installation.older_than('vms_6.0'):
                    client_installation.os_access.run([
                        'copy',
                        r'c:\windows\system32\opengl32sw.dll',
                        client_installation.get_binary_path().parent / 'opengl32.dll',
                        ])
                yield ClientStand(vm, client_installation)
            except Exception:
                vm.vm_control.take_screenshot(self._artifacts_dir / 'vm_client_exception.png')
                raise


class BenchmarkStand:

    def __init__(self, vm: VM, installation: VmsBenchmarkInstallation):
        self._vm = vm
        self._installation = installation

    def vm(self) -> VM:
        return self._vm

    def installation(self) -> VmsBenchmarkInstallation:
        return self._installation

    def os_access(self) -> OsAccess:
        return self._vm.os_access


class ClientStand:

    def __init__(self, vm: VM, installation: WindowsClientInstallation):
        self._vm = vm
        self._installation = installation

    def vm(self) -> VM:
        return self._vm

    def start_desktop_client(
            self,
            username: str,
            password: str,
            server_ip: str,
            ) -> TestKit:
        server_port = 7001
        self._installation.prepare_and_start(
            connect_from_command_line(server_ip, server_port, username, password))
        port_mapping = self._vm.vm_control.port_map()
        testkit_api = self._installation.connect_testkit(
            timeout=60, testkit_port=port_mapping['tcp'][7012])
        hid = HID(testkit_api)
        MainWindow(testkit_api, hid).activate()
        attempt = 0
        while True:
            attempt += 1
            try:
                ResourceTree(testkit_api, hid).wait_for_current_user()
            except CurrentUserNodeNotFound:
                if attempt >= 3:
                    raise
                time.sleep(10)
            else:
                break
        return testkit_api

    def installation(self) -> WindowsClientInstallation:
        return self._installation


def make_changed_vm_configuration(
        vm_configuration: VBoxSnapshotTemplate, ram: int, cpu: int) -> VBoxSnapshotTemplate:
    return vm_configuration.__class__(vm_configuration.name(), ram, cpu, vm_configuration._access_settings)


def _find_installer_supplier(url: str, os_name: str) -> ClassicInstallerSupplier:
    # The Artifactory structure for release versions differs from that of development versions.
    if not url.startswith('https://artifactory.us.nxteam.dev/artifactory/release-vms/default/'):
        return ClassicInstallerSupplier(url)
    base_url = url.rstrip('/')
    if os_name.startswith('ubuntu'):
        installers_url = f'{base_url}/linux/'
    elif os_name.startswith('win'):
        installers_url = f'{base_url}/windows/'
    else:
        raise InstallerNotFound(f"{os_name} is not supported in {url}")
    return ClassicInstallerSupplier(installers_url)


_logger = logging.getLogger(__name__)
