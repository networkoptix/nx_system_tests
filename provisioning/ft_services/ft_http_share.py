# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from provisioning import InstallCommon
from provisioning._core import Fleet
from provisioning._core import Run
from provisioning.fleet import beg_ft001
from provisioning.fleet import beg_ft002
from provisioning.fleet import sc_ft
from provisioning.fleet import sc_ft003_master

_logger = logging.getLogger(__name__)

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    Fleet.compose([sc_ft003_master, sc_ft, beg_ft001, beg_ft002]).run([
        # Add user, issue certificates.
        Run('sudo DEBIAN_FRONTEND=noninteractive apt-get install -y nginx-core libnginx-mod-http-perl'),
        Run('sudo -u ft mkdir -p ~ft/.cache/nx-func-tests-work-dir'),
        Run('sudo chmod o+rX ~ft/.cache/nx-func-tests-work-dir'),
        Run('sudo -u ft mkdir -p ~ft/.cache/nx-func-tests/vm-templates'),
        Run('sudo chmod o+rwX ~ft/.cache/nx-func-tests/vm-templates'),
        Run('sudo rm -f /etc/nginx/sites-enabled/default'),
        InstallCommon('ft', 'provisioning/ft_services/home.us.nginx.conf', '/etc/nginx/sites-available/'),
        Run('sudo ln -s -f /etc/nginx/sites-available/home.us.nginx.conf /etc/nginx/sites-enabled/home'),
        Run('sudo nginx -t'),
        Run('sudo systemctl reload nginx'),
        ])
