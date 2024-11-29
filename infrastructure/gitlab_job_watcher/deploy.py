# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from pathlib import Path

from provisioning import InstallSecret
from provisioning.fleet import sc_ft003_master
from provisioning.ft_services.python_services import FetchRepo
from provisioning.ft_services.python_services import LaunchSimpleSystemdService
from provisioning.ft_services.python_services import PrepareVenv


def main():
    sc_ft003_master.run([
        InstallSecret('ft', '~/.config/.secrets/slack_gitlab_failures_token.txt', '~ft/.config/.secrets/'),
        FetchRepo('ft', '~ft/gitlab_job_watcher/ft'),
        PrepareVenv('ft', '~ft/gitlab_job_watcher/ft', 'infrastructure'),
        LaunchSimpleSystemdService(
            'ft',
            Path(__file__, '../gitlab_job_watcher.service').resolve(),
            ),
        ])


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    main()
