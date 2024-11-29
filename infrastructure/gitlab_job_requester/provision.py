# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from pathlib import Path

from infrastructure._provisioning import SimpleServiceConfiguration
from infrastructure._provisioning import provision
from provisioning import CompositeCommand
from provisioning import InstallSecret
from provisioning.fleet import sc_ft003_master


def main():
    configuration = _GitLabJobRequester(
        sc_ft003_master,
        Path(__file__).with_name('gitlab_job_requester.service'),
        )
    provision(configuration)
    return 0


class _GitLabJobRequester(SimpleServiceConfiguration):

    def __init__(self, fleet, service_file):
        super().__init__(fleet, service_file)
        self._deploy = CompositeCommand([
            # InstallSecret('ft', '~/.config/.secrets/runner_token_fast.txt', '~ft/.config/.secrets/'),
            # InstallSecret('ft', '~/.config/.secrets/runner_token_batches_ft.txt', '~ft/.config/.secrets/'),
            # InstallSecret('ft', '~/.config/.secrets/runner_token_batches_gui.txt', '~ft/.config/.secrets/'),
            # InstallSecret('ft', '~/.config/.secrets/runner_token_ft_installation.txt', '~ft/.config/.secrets/'),
            # InstallSecret('ft', '~/.config/.secrets/runner_token_snapshots_jetsonnano.txt', '~ft/.config/.secrets/'),
            # InstallSecret('ft', '~/.config/.secrets/runner_token_snapshots_orinnano.txt', '~ft/.config/.secrets/'),
            # InstallSecret('ft', '~/.config/.secrets/runner_token_snapshots_rpi4.txt', '~ft/.config/.secrets/'),
            # InstallSecret('ft', '~/.config/.secrets/runner_token_snapshots_rpi5.txt', '~ft/.config/.secrets/'),
            # InstallSecret('ft', '~/.config/.secrets/runner_token_cloud_portal_tests.txt', '~ft/.config/.secrets/'),
            self._deploy,
            ])


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    exit(main())
