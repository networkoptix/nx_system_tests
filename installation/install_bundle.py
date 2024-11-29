# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import os
from argparse import ArgumentParser
from typing import cast

from ca import default_ca
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import WindowsBundleInstallation
from installation import WindowsServerInstallation
from mediaserver_scenarios.distrib_argparse_action import DistribArgparseAction
from os_access import WindowsAccess
from vm.default_vm_pool import public_default_vm_pool
from vm.default_vm_pool import vm_types


def main():
    parser = ArgumentParser(description='Bundle image builder')
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
            "Dry run: Would install bundle on %r with %s installers",
            args.os_name, args.distrib_url)
        return
    installer_supplier = ClassicInstallerSupplier(args.distrib_url)
    run_dir = get_run_dir()
    vm_pool = public_default_vm_pool(run_dir)
    with vm_pool.clean_vm(vm_types[args.os_name]) as vm:
        vm.ensure_started(run_dir)
        distrib = installer_supplier.distrib()
        win_access = cast(WindowsAccess, vm.os_access)
        version = distrib.version()
        customization = distrib.customization()
        installer = installer_supplier.upload_bundle_installer(vm.os_access)
        WindowsBundleInstallation(win_access, customization, version).install(installer)
        server_installation = WindowsServerInstallation(win_access, customization)
        server_installation.init_key_pair(default_ca().generate_key_and_cert(vm.os_access.address))
        server_installation.stop(already_stopped_ok=True)
        server_installation.check_for_error_logs()
        installer.unlink()


_logger = logging.getLogger("vbox")

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)7s %(name)s %(message).5000s")
    main()
