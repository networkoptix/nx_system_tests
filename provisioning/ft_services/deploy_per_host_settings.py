# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from provisioning._core import Fleet
from provisioning._core import Run
from provisioning.fleet import sc_ft
from provisioning.fleet import sc_ft002_cloud
from provisioning.fleet import sc_ft003_master


def main():
    """Remove or roll out temporary per-host settings.

    Deploy settings to match updated environment,
    while older commits with old values in config.ini are sometimes used.
    """
    sc = Fleet.compose([
        sc_ft003_master,
        sc_ft002_cloud,
        sc_ft,
        ])
    sc.run([
        Run('sudo -u ft rm ~ft/.config/nx_func_tests.ini'),
        # Run('echo "[*]" | sudo -u ft tee -a ~ft/.config/nx_func_tests.ini'),
        # Run('echo "qwe=123" | sudo -u ft tee -a ~ft/.config/nx_func_tests.ini'),
        ])


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    main()
