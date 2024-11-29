# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import os
from argparse import ArgumentParser

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import DpkgClientInstallation
from installation import WindowsClientInstallation
from installation._base_installation import OsNotSupported
from mediaserver_scenarios.distrib_argparse_action import DistribArgparseAction
from vm.default_vm_pool import public_default_vm_pool
from vm.default_vm_pool import vm_types


def main():
    parser = ArgumentParser(description='Client image builder')
    parser.add_argument('--installers-url', action=DistribArgparseAction)
    parser.add_argument(
        '--os-name',
        dest="os_name",
        help="Operation System name",
        choices=["ubuntu18", "ubuntu20", "ubuntu22", "ubuntu24", "win10", "win11"],
        required=True)
    args = parser.parse_args()
    if os.getenv('DRY_RUN'):
        _logger.info(
            "Dry run: Would install client on %r with %s installers",
            args.os_name, args.distrib_url)
        return
    installer_supplier = ClassicInstallerSupplier(args.distrib_url)
    run_dir = get_run_dir()
    vm_pool = public_default_vm_pool(run_dir)
    with vm_pool.clean_vm(vm_types[args.os_name]) as vm:
        vm.ensure_started(run_dir)
        distrib = installer_supplier.distrib()
        for installation_cls in (DpkgClientInstallation, WindowsClientInstallation):
            try:
                installation = installation_cls(vm.os_access, distrib.customization(), distrib.version())
                break
            except OsNotSupported:
                continue
        else:
            raise RuntimeError(f"No installation types exist for {vm.os_access!r}")
        try:
            installer = installer_supplier.upload_client_installer(vm.os_access)
            installation.install(installer)
            installer.unlink()
        finally:
            installation.collect_artifacts(run_dir)
            vm.os_access.download_system_logs(run_dir)


_logger = logging.getLogger("vbox")

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)7s %(name)s %(message).5000s")
    main()
