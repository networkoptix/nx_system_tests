# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from provisioning import Run
from provisioning._core import Input
from provisioning.fleet import sc_ft003_master


def main():
    sc_ft003_master.run([
        # Mimic repo dir structure.
        Input('infrastructure/ft_view/pgadmin4/pgadmin4', 'sudo install /dev/stdin /etc/nginx/sites-available/pgadmin4 -D -o ft -g ft'),
        Run('sudo ln -s -f ../sites-available/pgadmin4 /etc/nginx/sites-enabled/'),
        Run('sudo systemctl reload nginx'),
        # Manual action: Configure DNS records for the domain.
        ])


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    main()
