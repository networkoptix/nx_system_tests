# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from provisioning import InstallCommon
from provisioning._core import Run
from provisioning.fleet import sc_ft002_cloud


def main():
    sc_ft002_cloud.run([
        Run('sudo -u ft chmod a+rX ~ft'),
        Run('sudo -u ft mkdir -p ~ft/.cache/nx-func-tests-work-dir'),
        Run('sudo chmod -R o+rX ~ft/.cache/nx-func-tests-work-dir'),
        InstallCommon('root', 'provisioning/sc-ft002/ft_runs.conf', '/etc/nginx/sites-available/'),
        InstallCommon('root', 'provisioning/sc-ft002/cloud.nxft.dev.conf', '/etc/nginx/sites-available/'),
        InstallCommon('root', 'provisioning/sc-ft002/jenkins.cloud.nxft.dev.conf', '/etc/nginx/sites-available/'),
        InstallCommon('root', 'provisioning/sc-ft002/comparison_control_panel.conf', '/etc/nginx/sites-available/'),
        Run('sudo ln -s -f ../sites-available/ft_runs.conf /etc/nginx/sites-enabled/ft_runs.conf'),
        Run('sudo ln -s -f ../sites-available/cloud.nxft.dev.conf /etc/nginx/sites-enabled/cloud.nxft.dev.conf'),
        Run('sudo ln -s -f ../sites-available/jenkins.cloud.nxft.dev.conf /etc/nginx/sites-enabled/jenkins.cloud.nxft.dev.conf'),
        Run('sudo ln -s -f ../sites-available/comparison_control_panel.conf /etc/nginx/sites-enabled/comparison_control_panel.conf'),
        Run('sudo nginx -t'),
        Run('sudo systemctl reload nginx'),
        ])


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    main()
