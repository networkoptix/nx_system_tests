# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from pathlib import Path

from infrastructure._provisioning import ProvisionConfiguration
from infrastructure._provisioning import provision
from provisioning import Command
from provisioning import CompositeCommand
from provisioning import InstallCommon
from provisioning.fleet import sc_ft003_master
from provisioning.ft_services.python_services import SystemCtl
from provisioning.ft_services.python_services import UploadSystemdFile


def main():
    service_file = Path(__file__).with_name('message_broker.service')
    configuration = ProvisionConfiguration(
        service_file.name,
        sc_ft003_master,
        deploy=CompositeCommand([
            # Redis installation is not idempotent yet and need to be done only
            # once on the first deployment.
            # Run('sudo -u ft curl https://download.redis.io/redis-stable.tar.gz -L -o ~ft/redis-stable.tar.gz'),
            # Run('sudo -u ft tar -xz -f ~ft/redis-stable.tar.gz -C ~ft/'),
            # Run('sudo -u ft make -C ~ft/redis-stable/'),

            InstallCommon('ft', '_internal/redis.conf', '~ft/redis-stable/'),
            UploadSystemdFile('ft', service_file),
            SystemCtl('ft', 'daemon-reload'),
            SystemCtl('ft', 'restart', service_file.name),
            SystemCtl('ft', 'enable', service_file.name),
            ]),
        cleanup=_ForbiddenCommand('Redis service cleanup must not be automated'),
        start_after_failure=SystemCtl('ft', 'start', service_file.name),
        )
    provision(configuration)
    return 0


class _ForbiddenCommand(Command):

    def __init__(self, description):
        self._description = description

    def run(self, host: str):
        raise RuntimeError(self._description)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    exit(main())
