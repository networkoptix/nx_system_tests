# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import os
import sys

from make_venv import run_in_venv

if __name__ == '__main__':
    sys.exit(run_in_venv([
        'arm_tests/install_client.py',
        '--model', 'raspberry4',
        '--arch', 'x64',
        '--os', 'raspbian12',
        '--installers-url', os.environ['DISTRIB_URL'],
        ]))
