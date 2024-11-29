# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from provisioning import InstallCommon
from provisioning._core import Run
from provisioning._users import AddGroup
from provisioning.fleet import sc_ft003_master


def main():
    sc_ft003_master.run([
        AddGroup('prerequisites'),
        Run('sudo chgrp -R prerequisites ~ft/prerequisites'),
        Run('sudo chmod -R g+rw ~ft/prerequisites'),
        InstallCommon('ft', 'provisioning/ft_services/prerequisites.us.nginx.conf', '/etc/nginx/sites-available/'),
        Run('sudo ln -s -f /etc/nginx/sites-available/prerequisites.us.nginx.conf /etc/nginx/sites-enabled/prerequisites'),
        Run('sudo systemctl reload nginx'),
        ])


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    main()
