# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from provisioning import InstallCommon
from provisioning import Run
from provisioning.fleet import sc_ft003_master

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    sc_ft003_master.run([
        InstallCommon('ft', 'infrastructure/ft_view/ft-view.us.nginx.conf', '/etc/nginx/sites-available/'),
        Run('sudo ln -s -f /etc/nginx/sites-available/ft-view.us.nginx.conf /etc/nginx/sites-enabled/ft-view'),
        Run('sudo systemctl reload nginx'),
        # Manual action: Configure DNS records for the domain.
        ])
