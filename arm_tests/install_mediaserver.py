# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import os
import time
from argparse import ArgumentParser
from contextlib import closing

from arm_tests.arm_manager_client import LowPriorityMarket
from arm_tests.machine_description import get_machine_description
from arm_tests.machines_market import MediaserverSnapshot
from ca import default_ca
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import InstallerSupplier
from installation import Mediaserver
from installation import make_mediaserver_installation
from mediaserver_api import MediaserverApi
from mediaserver_api import MediaserverApiV0
from os_access import RemotePath


def _install(mediaserver: Mediaserver, installer_path: RemotePath):
    mediaserver.install(installer_path)
    api = MediaserverApiV0(mediaserver.base_url())
    _wait_online(api, timeout_sec=15)
    mediaserver.init_api(api)
    mediaserver.examine()
    mediaserver.stop()
    mediaserver.check_for_error_logs()


def _wait_online(api: MediaserverApi, timeout_sec: float):
    end_at = time.monotonic() + timeout_sec
    while True:
        if api.is_online():
            return
        if end_at < time.monotonic():
            raise RuntimeError(f"{api} is not ready after {timeout_sec} sec")
        time.sleep(0.5)


def _prepare_image(installer_supplier: InstallerSupplier, snapshot: MediaserverSnapshot):
    artifacts_dir = get_run_dir()
    with snapshot.open(LowPriorityMarket()) as running_machine:
        with closing(running_machine.get_os_access()) as os_access:
            customization = installer_supplier.distrib().customization()
            mediaserver = make_mediaserver_installation(os_access, customization)
            installer = installer_supplier.upload_server_installer(os_access)
            mediaserver.init_key_pair(default_ca().generate_key_and_cert(os_access.address))
            try:
                _install(mediaserver, installer)
            finally:
                logging.info("Collecting image build artifacts into %s ...", artifacts_dir)
                mediaserver.collect_artifacts(artifacts_dir)
                installer.unlink()
            mediaserver.remove_data_from_previous_runs()
            mediaserver.clean_auto_generated_config_values()
            mediaserver.enable_saving_console_output()
            mediaserver.set_common_config_values()
        running_machine.commit()


_logger = logging.getLogger(__name__)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG, format="%(asctime)s %(levelname)7s %(name)s %(message).5000s")
    parser = ArgumentParser(description='Image builder')
    parser.add_argument(
        '--installers-url',
        dest='installers',
        required=True,
        help='URL for installers of same version and customization.')
    parser.add_argument(
        '--model',
        dest='model',
        required=True,
        help='ARM machine model to install mediaserver on',
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
        _logger.info("Dry Run: Would create ARM snapshot with args %s", args)
        exit(0)
    default_ca().add_to_env_vars()
    mediaserver_installer_supplier = ClassicInstallerSupplier(args.installers)
    mediaserver_snapshot = MediaserverSnapshot(get_machine_description(args), args.installers)
    _prepare_image(mediaserver_installer_supplier, mediaserver_snapshot)
