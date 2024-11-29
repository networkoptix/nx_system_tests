# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import os
from argparse import ArgumentParser
from contextlib import closing
from contextlib import contextmanager

from arm_tests.arm_manager_client import LowPriorityMarket
from arm_tests.machine_description import get_machine_description
from arm_tests.machines_market import ClientSnapshot
from ca import default_ca
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import DpkgClientInstallation
from installation import InstallerSupplier


def _test_install_client(installer_supplier: InstallerSupplier, snapshot: ClientSnapshot):
    with snapshot.open(LowPriorityMarket()) as running_machine:
        with closing(running_machine.get_os_access()) as os_access:
            customization = installer_supplier.distrib().customization()
            installer_path = installer_supplier.upload_client_installer(os_access)
            client_installation = DpkgClientInstallation(
                os_access, customization, installer_supplier.distrib().version())
            with _gathered_artifacts(client_installation):
                client_installation.install(installer_path)
                client_installation.install_ca(default_ca().cert_path)
                with client_installation.opened_client(testkit_connect_timeout=60) as opened_client:
                    opened_client.wait_for_start()


@contextmanager
def _gathered_artifacts(client_installation: DpkgClientInstallation):
    try:
        yield
    finally:
        client_installation.collect_artifacts(get_run_dir())


_logger = logging.getLogger(__name__)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG, format="%(asctime)s %(levelname)7s %(name)s %(message).5000s")
    parser = ArgumentParser(description='Client installer')
    parser.add_argument(
        '--installers-url',
        dest='installers',
        required=True,
        help='URL for installers of same version and customization.')
    parser.add_argument(
        '--model',
        dest='model',
        required=True,
        help='ARM machine model',
        )
    parser.add_argument(
        '--arch',
        dest='arch',
        required=True,
        help='ARM architecture',
        )
    parser.add_argument(
        '--os',
        dest='os',
        required=True,
        help='ARM board Operation System',
        )
    args = parser.parse_args()
    if os.getenv('DRY_RUN'):
        log_template = (
            "Dry Run: "
            "Would attempt to install GUI client with arguments "
            "distrib_url %s, model %s, architecture %s and OS %s"
            )
        _logger.info(log_template, args.installers, args.model, args.arch, args.os)
        exit(0)
    default_ca().add_to_env_vars()
    client_installer_supplier = ClassicInstallerSupplier(args.installers)
    client_snapshot = ClientSnapshot(get_machine_description(args), args.installers)
    _test_install_client(client_installer_supplier, client_snapshot)
