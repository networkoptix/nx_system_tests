# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from provisioning import AddPubKey
from provisioning import AddUser
from provisioning import Fleet
from provisioning import InstallCommon
from provisioning import InstallSecret
from provisioning import RepoPubKey
from provisioning import Run
from provisioning._core import Input
from provisioning._users import AddGroup
from provisioning._users import AddUserToGroup

_logger = logging.getLogger(__name__)


def main():
    fleet = Fleet([
        'sc-ft002.nxlocal',
        ])
    fleet.run([
        AddGroup('guests'),
        AddUser('ci'),
        Run('sudo chmod o+rX ~ci'),
        AddUserToGroup('ci', 'guests'),
        # CUT: Personal accounts configuration
        AddPubKey('ci', RepoPubKey('ci.rsa.pub')),
        AddPubKey('ci', RepoPubKey('ci.ed25519.pub')),
        AddPubKey('ci', RepoPubKey('gsovetov.rsa.pub')),
        AddPubKey('ci', RepoPubKey('gsovetov2.rsa.pub')),
        # CUT: Personal accounts configuration
        AddUser('sre'),
        Run('sudo chmod o+rX ~sre'),
        AddUserToGroup('sre', 'guests'),
        # CUT: Personal accounts configuration
        AddPubKey('sre', RepoPubKey('gsovetov.rsa.pub')),
        AddPubKey('sre', RepoPubKey('gsovetov2.rsa.pub')),
        AddPubKey('sre', RepoPubKey('sre.rsa.pub')),
        AddPubKey('sre', RepoPubKey('sre2.rsa.pub')),
        # CUT: Personal accounts configuration
        AddUser('guest'),
        Run('sudo chmod o+rX ~guest'),
        AddUserToGroup('guest', 'guests'),
        # CUT: Personal accounts configuration
        AddPubKey('guest', RepoPubKey('gsovetov.rsa.pub')),
        AddPubKey('guest', RepoPubKey('gsovetov2.rsa.pub')),
        # CUT: Personal accounts configuration

        InstallCommon('root', 'run_in_unique_dir.py', '/opt/'),
        InstallCommon('root', 'run_from_git.py', '/opt/'),

        Input('provisioning/ft_services/guests_group.sshd.conf', 'sudo sshd -T -f /dev/input'),
        InstallSecret('root', 'provisioning/ft_services/guests_group.sshd.conf', '/etc/ssh/sshd_config.d/'),
        Run('sudo systemctl reload ssh.service'),
        ])


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    main()
