# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from provisioning import AddPubKey
from provisioning import InstallSecret
from provisioning import RepoPubKey
from provisioning._core import Fleet
from provisioning._core import Input
from provisioning._core import Run
from provisioning._users import AddUser
from provisioning.fleet import beg_ft001
from provisioning.fleet import beg_ft002
from provisioning.fleet import sc_ft
from provisioning.fleet import sc_ft002_cloud
from provisioning.fleet import sc_ft003_master

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    Fleet.compose([sc_ft003_master, sc_ft, beg_ft001]).run([
        AddUser('ft'),
        Run('sudo usermod -s /bin/bash ft'),
        Run('sudo -u ft chmod a+rX ~ft'),
        Run('sudo loginctl enable-linger ft'),
        ])
    # Master must be able to log in to self and worker hosts.
    sc_ft003_master.run([
        InstallSecret('ft', '~/.ssh/sc_ft003_master.rsa', '~ft/.ssh/'),
        Input('provisioning/ft_services/sc_ft003_master.ssh.config', 'sudo install /dev/stdin ~ft/.ssh/config -o ft -g ft -m u=rw,go='),
        ])
    Fleet.compose([sc_ft003_master, sc_ft002_cloud, sc_ft, beg_ft001, beg_ft002]).run([
        AddPubKey('ft', RepoPubKey('sc_ft003_master.rsa.pub')),
        ])
    # Cache host keys, so future SSH connections works without warning
    sc_ft003_master.run([
        Run('sudo -u ft ssh -oStrictHostKeyChecking=accept-new sc-ft002 whoami'),
        Run('for i in {004..024}; do sudo -u ft ssh -oStrictHostKeyChecking=accept-new sc-ft$i whoami; done'),
        Run('for i in {001..002}; do sudo -u ft ssh -oStrictHostKeyChecking=accept-new beg-ft$i whoami; done'),
        ])
    # Worker must be able to log in to self and other workers.
    sc_ft.run([
        InstallSecret('ft', '~/.ssh/sc_ft.rsa', '~ft/.ssh/'),
        AddPubKey('ft', RepoPubKey('sc_ft.rsa.pub')),
        Input('provisioning/ft_services/sc_ft.ssh.config', 'sudo install /dev/stdin ~ft/.ssh/config -o ft -g ft -m u=rw,go='),
        ])
    # Cache host keys, so future SSH connections works without warning
    sc_ft.run([
        Run('for i in {004..024}; do sudo -u ft ssh -oStrictHostKeyChecking=accept-new sc-ft$i whoami; done'),
        ])
