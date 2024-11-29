# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from provisioning import AddUser
from provisioning import Run
from provisioning._users import AddUserToGroup
from provisioning.fleet import beg_ft002

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    beg_ft002.run([
        Run('sudo apt install -y git ssh-askpass authbind'),
        AddUser('ft'),
        AddUserToGroup('ft', 'qcow2targetgroup'),
        Run('sudo touch /etc/authbind/byport/69'),
        Run('sudo chown root:ft /etc/authbind/byport/69'),
        Run('sudo chmod 650 /etc/authbind/byport/69'),
        Run('sudo -u ft chmod a+rX ~ft'),
        Run('sudo loginctl enable-linger ft'),
        ])
