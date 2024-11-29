# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from contextlib import AbstractContextManager
from contextlib import ExitStack
from contextlib import contextmanager
from pathlib import Path
from subprocess import CalledProcessError
from typing import cast

from ca import default_ca
from config import global_config
from installation import InstallerSupplier
from installation import WindowsClientInstallation
from installation import WindowsMobileClient
from installation import WindowsServerInstallation
from mediaserver_api import MediaserverApiV3
from mediaserver_scenarios.provisioned_mediaservers import prepared_mediaserver_vm
from os_access import WindowsAccess
from os_access.screen_recorder.vlc import VLCScreenRecordingWindows
from vm.client_vm_pool import vm_types
from vm.default_vm_pool import public_default_vm_pool
from vm.nxwitness_snapshots.bundle_plugin import BundlePlugin
from vm.nxwitness_snapshots.client_plugin import ClientPlugin
from vm.vm import VM


class _WindowsStand:

    def __init__(self, vm: VM):
        self._vm = vm

    def vm(self) -> VM:
        return self._vm

    def os_access(self) -> WindowsAccess:
        return cast(WindowsAccess, self._vm.os_access)

    def get_screen_recorder(self) -> VLCScreenRecordingWindows:
        return VLCScreenRecordingWindows(
            self._vm.os_access, self._vm.os_access.get_port('tcp', 12312))

    def set_screen_resolution(self, width: int, height: int, color_depth: int):
        self._vm.vm_control.set_screen_mode(width, height, color_depth)


class DesktopClientStand(_WindowsStand):

    def __init__(self, vm: VM, installation: WindowsClientInstallation):
        super().__init__(vm)
        self._installation = installation

    def installation(self) -> WindowsClientInstallation:
        return self._installation

    def get_testkit_port(self) -> int:
        return self._vm.os_access.get_port('tcp', 7012)


class BundleStand(_WindowsStand):

    def __init__(
            self,
            vm: VM,
            client_installation: WindowsClientInstallation,
            server_installation: WindowsServerInstallation,
            ):
        super().__init__(vm)
        self._client_installation = client_installation
        self._server_installation = server_installation

    def client_installation(self) -> WindowsClientInstallation:
        return self._client_installation

    def server_installation(self) -> WindowsServerInstallation:
        return self._server_installation


class DesktopMobileClientStand(_WindowsStand):

    def __init__(self, vm: VM, installation: WindowsMobileClient):
        super().__init__(vm)
        self._installation = installation

    def installation(self) -> WindowsMobileClient:
        return self._installation


class DesktopMachinePool:
    def __init__(
            self,
            artifact_dir: Path,
            installer_supplier: InstallerSupplier,
            ):
        self._artifacts_dir = artifact_dir
        self._artifacts_dir.mkdir()
        self._installer_supplier = installer_supplier
        self._vm_pool = public_default_vm_pool(self._artifacts_dir)
        default_ca().add_to_env_vars()

    @contextmanager
    def client_stand(self) -> AbstractContextManager[DesktopClientStand]:
        distrib = self._installer_supplier.distrib()
        client_plugin = ClientPlugin(self._installer_supplier)
        client_installation = None
        with ExitStack() as stack:
            vm = stack.enter_context(self._vm_pool.vm_created(client_plugin, vm_types['win11']))
            try:
                vm.ensure_started(self._artifacts_dir)
                windows_access = cast(WindowsAccess, vm.os_access)
                stack.enter_context(windows_access.prepared_one_shot_vm(self._artifacts_dir))
                _configure_internet_explorer(windows_access)
                # For the Client rendering, the MESA OpenGL library is used for software rendering.
                # By default, this library uses a number of threads equal to the number of CPU cores,
                # which may overload the CPU. Set the number of threads to 0 to avoid this.
                windows_access.run(['setx', 'LP_NUM_THREADS', '0', '/M'])
                client_installation = WindowsClientInstallation(
                    windows_access, distrib.customization(), distrib.version())
                stack.callback(client_installation.collect_artifacts, self._artifacts_dir)
                client_installation.configure_for_tests()
                client_installation.setup_full_crash_dump()
                client_installation.set_ini('nx_utils.ini', {'assertCrash': '1'})
                yield DesktopClientStand(vm, client_installation)
            except Exception:
                if client_installation is not None:
                    client_installation.take_backtrace(self._artifacts_dir)
                vm.vm_control.take_screenshot(self._artifacts_dir / 'vm_client_exception.png')
                raise
            finally:
                vm.vm_control.copy_logs(self._artifacts_dir)

    @contextmanager
    def bundle_stand(self) -> AbstractContextManager[BundleStand]:
        distrib = self._installer_supplier.distrib()
        bundle_plugin = BundlePlugin(self._installer_supplier)
        client_installation = None
        with ExitStack() as stack:
            vm = stack.enter_context(self._vm_pool.vm_created(bundle_plugin, vm_types['win11']))
            try:
                vm.ensure_started(self._artifacts_dir)
                windows_access = cast(WindowsAccess, vm.os_access)
                stack.enter_context(windows_access.prepared_one_shot_vm(self._artifacts_dir))
                windows_access.networking.allow_multicast()  # For automatic discovery of the Mediaserver
                _configure_internet_explorer(windows_access)
                # For the Client rendering, the MESA OpenGL library is used for software rendering.
                # By default, this library uses a number of threads equal to the number of CPU cores,
                # which may overload the CPU. Set the number of threads to 0 to avoid this.
                windows_access.run(['setx', 'LP_NUM_THREADS', '0', '/M'])
                client_installation = WindowsClientInstallation(
                    windows_access, distrib.customization(), distrib.version())
                stack.callback(client_installation.collect_artifacts, self._artifacts_dir)
                client_installation.configure_for_tests()
                client_installation.setup_full_crash_dump()
                client_installation.set_ini('nx_utils.ini', {'assertCrash': '1'})
                server_installation = stack.enter_context(
                    prepared_mediaserver_vm(vm, MediaserverApiV3, self._artifacts_dir))
                server_installation.update_conf({
                    'checkForUpdateUrl': 'http://127.0.0.1:8080',  # TODO: Use fake server responding with small updates.
                    })
                yield BundleStand(vm, client_installation, server_installation)
            except Exception:
                if client_installation is not None:
                    client_installation.take_backtrace(self._artifacts_dir)
                vm.vm_control.take_screenshot(self._artifacts_dir / 'vm_bundle_exception.png')
                raise
            finally:
                vm.vm_control.copy_logs(self._artifacts_dir)

    @contextmanager
    def mobile_client_stand(self) -> AbstractContextManager[DesktopMobileClientStand]:
        with ExitStack() as stack:
            vm = stack.enter_context(self._vm_pool.clean_vm(vm_types['win11']))
            try:
                vm.ensure_started(self._artifacts_dir)
                windows_access = cast(WindowsAccess, vm.os_access)
                stack.enter_context(windows_access.prepared_one_shot_vm(self._artifacts_dir))
                windows_access.networking.allow_multicast()  # For automatic discovery of the Mediaserver
                _configure_internet_explorer(windows_access)
                # For the Client rendering, the MESA OpenGL library is used for software rendering.
                # By default, this library uses a number of threads equal to the number of CPU cores,
                # which may overload the CPU. Set the number of threads to 0 to avoid this.
                windows_access.run(['setx', 'LP_NUM_THREADS', '0', '/M'])
                mobile_client_installation = WindowsMobileClient(windows_access)
                installer = self._installer_supplier.upload_mobile_client(windows_access)
                mobile_client_installation.install(installer)
                stack.callback(mobile_client_installation.collect_artifacts, self._artifacts_dir)
                mobile_client_installation.configure_for_tests()
                yield DesktopMobileClientStand(vm, mobile_client_installation)
            except Exception:
                vm.vm_control.take_screenshot(self._artifacts_dir / 'vm_mobile_client_exception.png')
                raise
            finally:
                vm.vm_control.copy_logs(self._artifacts_dir)


def _configure_internet_explorer(os_access: WindowsAccess):
    """Imitate first run setup of Internet Explorer to help WebView.

    Typically, a human user completes the wizard, opens the Cloud URL once,
    and forgets about it.
    """
    # Disable the first-run wizard of Internet Explorer for correct working
    # WebView (used in Desktop Client for CloudPanel and etc). It is need only
    # on a fresh system without updates, where Internet Explorer is the default
    # browser.
    # See: https://stackoverflow.com/questions/26550859/disable-internet-explorer-11-first-run-wizard/43496639#43496639
    os_access.registry.create_key(r'HKLM\SOFTWARE\Policies\Microsoft\Internet Explorer\Main')
    os_access.registry.set_dword(r'HKLM\SOFTWARE\Policies\Microsoft\Internet Explorer\Main', 'DisableFirstRunCustomize', 1)
    # To ensure the correct functioning of the WebView component, it is necessary to open
    # the Cloud URL in Internet Explorer or use Wget at least once.
    cloud_host = global_config.get('test_cloud_host')
    try:
        os_access.run(['powershell', 'wget', f'https://{cloud_host}'])
    except CalledProcessError:
        # Sometimes the IP addresses of the cloud host change, and that requires updating the
        # iptables configuration. While this can be problematic, it is not necessarily critical
        # for causing all GUI tests to fail. Therefore, only log the error.
        _logger.exception('Error opening cloud URL %s in Wget', cloud_host)


_logger = logging.getLogger(__name__)
