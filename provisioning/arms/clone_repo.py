# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from provisioning.fleet import beg_ft002
from provisioning.ft_services.python_services import FetchRepo

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    beg_ft002.run([
        FetchRepo('ft', '~ft/ft'),
        ])
