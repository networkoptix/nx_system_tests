# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from provisioning._core import Fleet
from provisioning._core import Run
from provisioning.fleet import sc_ft
from provisioning.fleet import sc_ft003_master
from provisioning.ft_runs._virtual_box import InstallVirtualBox

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    sc_ft003_master.run([
        # libvlc-bin is needed for real_camera_test unittests, because it is checking
        # GenericLinkConfig() that depends on VLC package, which is patched by us in vlc_server.py
        Run('sudo DEBIAN_FRONTEND=noninteractive apt-get install -y libvlc-bin'),
        ])
    Fleet.compose([sc_ft]).run([
        InstallVirtualBox(),
        Run('sudo DEBIAN_FRONTEND=noninteractive apt-get install -y python3-venv'),
        Run('sudo DEBIAN_FRONTEND=noninteractive apt-get install -y ffmpeg'),
        # See: https://tesseract-ocr.github.io/tessdoc/Installation.html
        # See: https://launchpad.net/~alex-p/+archive/ubuntu/tesseract-ocr5
        # The repository belongs to the current maintainer of Tesseract.
        Run('sudo add-apt-repository --ppa ppa:alex-p/tesseract-ocr5'),
        Run('sudo DEBIAN_FRONTEND=noninteractive apt-get install -y tesseract-ocr=5.3.2-1ppa1~jammy1'),
        ])
    sc_ft.run([
        # AddUserToGroup('ft', 'vboxusers'),
        ])
