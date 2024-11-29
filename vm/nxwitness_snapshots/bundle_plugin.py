# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import os
import shlex
from argparse import ArgumentParser
from contextlib import ExitStack
from pathlib import Path
from traceback import format_exception
from typing import cast

from _internal.service_registry import ft_view_reporter
from ca import default_ca
from directories import get_ft_snapshots_cache_root
from directories import get_run_dir
from directories import run_metadata
from directories import standardize_module_name
from directories.prerequisites import DefaultDistributionGroup
from infrastructure.ft_view.run_updates_reporter import StageReporter
from installation import ClassicInstallerSupplier
from installation import InstallerSupplier
from installation import WindowsClientInstallation
from installation._bundle_installation import WindowsBundleInstallation
from installation._windows_server_installation import WindowsServerInstallation
from mediaserver_scenarios.distrib_argparse_action import DistribArgparseAction
from os_access import OsAccess
from os_access import WindowsAccess
from runner.reporting.pretty_traceback import dump_traceback
from vm.client_vm_pool import vm_types
from vm.default_vm_pool import public_default_vm_pool
from vm.nxwitness_snapshots._plugin_interface import SnapshotPlugin


class BundlePlugin(SnapshotPlugin):

    def __init__(self, installer_supplier: InstallerSupplier):
        self._distrib = installer_supplier.distrib()
        self._installer_supplier = installer_supplier

    def __repr__(self):
        return f"BundlePlugin({self._installer_supplier!r})"

    def name_prefix(self, os_name):
        return self._distrib.bundle_dependent_prefix(os_name)

    def prepare(self, os_access: OsAccess, artifacts_dir: Path):
        win_access = cast(WindowsAccess, os_access)
        # Reset the Windows licensing status of the machine.
        # If the host has Internet access (on developers' machines, for example), Windows
        # automatically activates the temporary license. If the expiration date is less than 30
        # days away, a dialog window with the message "Your Windows license will expire soon"
        # appears on the screen. This breaks the GUI tests.
        win_access.run(['cscript', '//B', r'%windir%\system32\slmgr.vbs', '/rearm'])
        version = self._installer_supplier.distrib().version()
        customization = self._distrib.customization()
        installer = self._installer_supplier.upload_bundle_installer(win_access)
        WindowsBundleInstallation(win_access, customization, version).install(installer)
        server_installation = WindowsServerInstallation(win_access, customization)
        with ExitStack() as exit_stack:
            exit_stack.callback(self._configure_mediaserver, server_installation)
            exit_stack.callback(server_installation.collect_artifacts, artifacts_dir)
            server_installation.init_key_pair(default_ca().generate_key_and_cert(os_access.address))
            server_installation.stop(already_stopped_ok=True)
            server_installation.check_for_error_logs()
            client_installation = WindowsClientInstallation(win_access, customization, version)
            exit_stack.callback(client_installation.collect_artifacts, artifacts_dir)
            client_installation.configure_for_tests()
            client_installation.prepare_and_start([])
            client_installation.connect_testkit(timeout=120, testkit_port=os_access.get_port('tcp', 7012))
            client_installation.kill_client_process()
            installer.unlink()

    def _configure_mediaserver(self, mediaserver):
        mediaserver.clean_auto_generated_config_values()
        mediaserver.enable_saving_console_output()
        mediaserver.set_common_config_values()


def main():
    parser = ArgumentParser(description='Client image builder')
    parser.add_argument('--installers-url', action=DistribArgparseAction)
    parser.add_argument(
        '--os-name',
        dest="os_name",
        help="Operation System name",
        choices=["win10", "win11"],
        required=True)
    args = parser.parse_args()
    if os.getenv('DRY_RUN'):
        _logger.info(
            "Dry run: Would create %r snapshot with %s installers",
            args.os_name, args.distrib_url)
        return
    run_dir = get_run_dir()
    run_properties = {
        **run_metadata(),
        'run_cmdline': {
            'env.COMMIT': run_metadata()['run_ft_revision'],
            'exe': shlex.join(['python', '-m', 'make_venv']),
            'args': shlex.join(['-m', standardize_module_name(__file__), args.os_name]),
            'opt.--installers-url': args.distrib_url,
            'opt.--os-name': args.os_name,
            },
        }
    with StageReporter(ft_view_reporter, run_dir, run_properties) as reporter:
        print(f"Run URL: {reporter.get_run_url()}", flush=True)
        try:
            installer_supplier = ClassicInstallerSupplier(args.distrib_url)
            vm_pool = public_default_vm_pool(get_run_dir())
            bundle_plugin = BundlePlugin(installer_supplier)
            snapshot_uri = vm_pool.create_snapshot(bundle_plugin, vm_types[args.os_name])
            DefaultDistributionGroup().share_file(snapshot_uri, str(get_ft_snapshots_cache_root()))
        except Exception as e:
            _logger.exception("Snapshot: Exception")
            dump_traceback(e, run_dir)
            reporter.set_failed(''.join(format_exception(e)).rstrip())
            return 10
        else:
            reporter.set_passed()
            return 0


_logger = logging.getLogger("vbox")

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)7s %(name)s %(message).5000s")
    main()
