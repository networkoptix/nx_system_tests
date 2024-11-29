# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from pathlib import Path

from provisioning import InstallCommon
from provisioning import InstallSecret
from provisioning import Run
from provisioning.fleet import sc_ft003_master
from provisioning.ft_services.python_services import LaunchSimpleSystemdService


def main():
    sc_ft003_master.run([
        # Mimic repo dir structure.
        InstallCommon('ft', 'infrastructure/ft_view/oidc/oidc.py', '~ft/oidc/ft/infrastructure/ft_view/oidc/'),
        InstallSecret('ft', '~/.config/.secrets/us.nxft.dev-client-secret.txt', '~ft/.config/.secrets/'),
        InstallCommon('ft', 'infrastructure/ft_view/oidc/oidc-auth-request.conf', '/etc/nginx/snippets/'),
        InstallCommon('ft', 'infrastructure/ft_view/oidc/oidc-validate.conf', '/etc/nginx/snippets/'),
        InstallCommon('ft', 'infrastructure/ft_view/oidc/oidc-callback', '/etc/nginx/sites-available/'),
        Run('sudo ln -s -f ../sites-available/oidc-callback /etc/nginx/sites-enabled/'),
        InstallCommon('ft', 'infrastructure/ft_view/oidc/oidc-cache.conf', '/etc/nginx/conf.d/'),
        Run('sudo systemctl reload nginx'),
        LaunchSimpleSystemdService('ft', Path(__file__, '../oidc-backend.service').resolve()),
        # Manual action: Configure DNS records for the domain.
        # Manual action: Allow callback URL in Google Admin Console.
        ])


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    main()
