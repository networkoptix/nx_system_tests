# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from pathlib import Path

from provisioning import Run
from provisioning.fleet import beg_ft002

_dir = Path(__file__).parent

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    beg_ft002.run([
        # See: https://drive.google.com/drive/folders/1MVYP_9q0tSfN9XwEi0Fbl8LpttO6uE5a
        # 'arms' directory should be placed to /root manually.
        Run('sudo mkdir -p /mnt/storage/tftp/jetsonnano/x64/ubuntu18'),
        Run('sudo cp -r /root/arms/tftp/jetsonnano/x64/ubuntu18/* /mnt/storage/tftp/jetsonnano/x64/ubuntu18/'),
        Run('sudo mkdir -p /mnt/storage/tftp/raspberry4/x32/raspbian10'),
        Run('sudo cp -r /root/arms/tftp/raspberry4/x32/raspbian10/* /mnt/storage/tftp/raspberry4/x32/raspbian10/'),
        Run('sudo mkdir -p /mnt/storage/tftp/raspberry4/x32/raspbian11'),
        Run('sudo cp -r /root/arms/tftp/raspberry4/x32/raspbian11/* /mnt/storage/tftp/raspberry4/x32/raspbian11/'),
        Run('sudo mkdir -p /mnt/storage/tftp/raspberry4/x32/raspbian12'),
        Run('sudo cp -r /root/arms/tftp/raspberry4/x32/raspbian12/* /mnt/storage/tftp/raspberry4/x32/raspbian12/'),
        Run('sudo mkdir -p /mnt/storage/tftp/raspberry4/x64/raspbian11'),
        Run('sudo cp -r /root/arms/tftp/raspberry4/x64/raspbian11/* /mnt/storage/tftp/raspberry4/x64/raspbian11/'),
        Run('sudo mkdir -p /mnt/storage/tftp/raspberry4/x64/raspbian12'),
        Run('sudo cp -r /root/arms/tftp/raspberry4/x64/raspbian12/* /mnt/storage/tftp/raspberry4/x64/raspbian12/'),
        Run('sudo mkdir -p /mnt/storage/tftp/raspberry5/x32/raspbian12'),
        Run('sudo cp -r /root/arms/tftp/raspberry5/x32/raspbian12/* /mnt/storage/tftp/raspberry5/x32/raspbian12/'),
        Run('sudo mkdir -p /mnt/storage/tftp/raspberry5/x64/raspbian12'),
        Run('sudo cp -r /root/arms/tftp/raspberry5/x64/raspbian12/* /mnt/storage/tftp/raspberry5/x64/raspbian12/'),
        Run('sudo mkdir -p /mnt/storage/tftp/orin_nano/x64/ubuntu22'),
        Run('sudo cp -r /root/arms/tftp/orin_nano/x64/ubuntu22/* /mnt/storage/tftp/orin_nano/x64/ubuntu22'),
        Run('sudo chown -R ft:ft /root/arms/tftp'),
        ])
