# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from pathlib import Path

from provisioning import InstallCommon
from provisioning import Run
from provisioning.fleet import beg_ft002

_dir = Path(__file__).parent

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    beg_ft002.run([
        Run('sudo apt install -y sudo apt install nfs-kernel-server'),
        # See: https://drive.google.com/file/d/1oEpLQR725UQk3S8cr600jUkcJWNaNxoa/view
        # 'rpi3b_x64_raspbian12_f11b752a.tar.xz' should be placed to /root manually.
        Run('sudo mkdir -p /srv/nfs/raspberry3b/x64/raspbian12/f11b752a'),
        Run('sudo tar xf ./rpi3b_x64_raspbian12_f11b752a.tar.xz -C /srv/nfs/raspberry3b/x64/raspbian12/f11b752a'),
        InstallCommon('root', 'exports', '/etc/'),
        Run('sudo exportfs -ra'),
        Run('sudo systemctl restart nfs-kernel-server'),
        ])
