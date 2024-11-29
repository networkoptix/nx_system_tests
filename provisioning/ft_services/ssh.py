# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from provisioning._core import Fleet
from provisioning._known_hosts import AddOtherToOurKnownHosts
from provisioning.fleet import sc_ft
from provisioning.fleet import sc_ft003_master

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    Fleet.compose([sc_ft003_master, sc_ft]).run([
        AddOtherToOurKnownHosts('ft', 'gitlab.nxvms.dev', 'git', ''),
        ])
