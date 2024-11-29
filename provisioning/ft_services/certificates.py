# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from pathlib import Path

from provisioning import Run
from provisioning._ssh import ssh
from provisioning._ssh import ssh_write_file
from provisioning._users import AddUserToGroup
from provisioning.fleet import sc_ft003_master


def main():
    sc_ft003_master.run([
        # Install Docker
        # See: https://docs.docker.com/engine/install/ubuntu/
        Run('sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc'),
        Run('sudo chmod a+r /etc/apt/keyrings/docker.asc'),
        Run('echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu jammy stable" | sudo tee /etc/apt/sources.list.d/docker.list'),
        Run('sudo apt update'),
        Run('sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin'),
        AddUserToGroup('ft', 'docker'),
        ])
    master = 'sc-ft003.nxlocal'
    _issue_cert_for_other(master, [
        'sc-ft003.nxlocal',
        'sc-ft004.nxlocal',
        'sc-ft005.nxlocal',
        'sc-ft006.nxlocal',
        'sc-ft007.nxlocal',
        'sc-ft008.nxlocal',
        'sc-ft009.nxlocal',
        'sc-ft010.nxlocal',
        'sc-ft011.nxlocal',
        'sc-ft012.nxlocal',
        'sc-ft013.nxlocal',
        'sc-ft014.nxlocal',
        'sc-ft015.nxlocal',
        'sc-ft016.nxlocal',
        'sc-ft017.nxlocal',
        'sc-ft018.nxlocal',
        'sc-ft019.nxlocal',
        'sc-ft020.nxlocal',
        'sc-ft021.nxlocal',
        'sc-ft022.nxlocal',
        'sc-ft023.nxlocal',
        'sc-ft024.nxlocal',
        'beg-ft001.nxlocal',
        'beg-ft002.nxlocal',
        ])


def _issue_cert_for_other(master, hosts):
    fullchain, privkey = _certbot(master)
    cat_fullchain = ssh(master, f'sudo -u ft cat {fullchain}')
    cat_privkey = ssh(master, f'sudo -u ft cat {privkey}')
    for host in hosts:
        ssh(host, 'sudo -u ft mkdir -p ~ft/.config')
        ssh_write_file(host, 'ft', '~ft/.config/fullchain.pem', cat_fullchain.stdout)
        ssh_write_file(host, 'ft', '~ft/.config/privkey.pem', cat_privkey.stdout)
        ssh(host, 'sudo systemctl reload nginx')


def _certbot(master):
    # If shared volumes are created by Docker, they're owned by root.
    # And, therefore, inaccessible with normal user's permissions.
    ssh(master, 'sudo -u ft mkdir -p ~ft/.config/letsencrypt/{etc,log,lib,aws}')
    aws_conf = Path('~/.config/.secrets/certbot_route53_aws_config').expanduser().read_bytes()
    ssh_write_file(master, 'ft', '~ft/.config/letsencrypt/aws/config', aws_conf)
    ssh(master, (
        'sudo -Hu ft docker run --name certbot-dns-route53 '
        '-v ~ft/.config/letsencrypt/etc:/etc/letsencrypt '
        '-v ~ft/.config/letsencrypt/log:/var/log/letsencrypt '
        '-v ~ft/.config/letsencrypt/lib:/var/lib/letsencrypt '
        '-v ~ft/.config/letsencrypt/aws:/.aws '
        '-e AWS_CONFIG_FILE=/.aws/config '
        '--user "$(id -u ft):$(id -g ft)" '
        '--rm '
        'certbot/dns-route53 certonly --dns-route53 '
        '--non-interactive --agree-tos '
        '--email gsovetov@networkoptix.com '
        '--cert-name nxft.dev -d nxft.dev,*.nxft.dev,*.us.nxft.dev'))
    fullchain = '~ft/.config/letsencrypt/etc/live/nxft.dev/fullchain.pem'
    privkey = '~ft/.config/letsencrypt/etc/live/nxft.dev/privkey.pem'
    return fullchain, privkey


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    main()
