# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from pathlib import Path

from provisioning import InstallSecret
from provisioning._core import Input
from provisioning._users import NewUsers
from provisioning.fleet import Fleet
from provisioning.fleet import beg_ft001
from provisioning.fleet import sc_ft
from provisioning.fleet import sc_ft002_cloud

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    user_config = Path(__file__).with_name('ft_subusers.txt').read_text().rstrip()
    Fleet.compose([sc_ft, sc_ft002_cloud, beg_ft001]).run([
        Input('provisioning/sudoers.d/ft', 'sudo visudo -c -f /dev/stdin'),
        InstallSecret('root', 'provisioning/sudoers.d/ft', '/etc/sudoers.d/'),
        NewUsers(user_config),
        ])
