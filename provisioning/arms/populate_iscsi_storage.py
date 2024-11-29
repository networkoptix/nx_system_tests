# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from pathlib import Path

from provisioning import InstallCommon
from provisioning import Run
from provisioning.fleet import beg_ft002

_dir = Path(__file__).parent

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    storage_sizes = _dir / 'beg-ft002_storage_sizes'
    beg_ft002.run([
        # See: https://drive.google.com/drive/folders/1MVYP_9q0tSfN9XwEi0Fbl8LpttO6uE5a
        # 'arms' directory should be placed to /root manually.
        Run('sudo mkdir -p /mnt/storage/iscsi/jetsonnano/x64/ubuntu18'),
        Run('sudo cp -r /root/arms/iscsi/jetsonnano/x64/ubuntu18/* /mnt/storage/iscsi/jetsonnano/x64/ubuntu18/'),
        Run('sudo mkdir -p /mnt/storage/iscsi/raspberry4/x32/raspbian10'),
        Run('sudo cp -r /root/arms/iscsi/raspberry4/x32/raspbian10/* /mnt/storage/iscsi/raspberry4/x32/raspbian10/'),
        Run('sudo mkdir -p /mnt/storage/iscsi/raspberry4/x32/raspbian11'),
        Run('sudo cp -r /root/arms/iscsi/raspberry4/x32/raspbian11/* /mnt/storage/iscsi/raspberry4/x32/raspbian11/'),
        Run('sudo mkdir -p /mnt/storage/iscsi/raspberry4/x32/raspbian12'),
        Run('sudo cp -r /root/arms/iscsi/raspberry4/x32/raspbian12/* /mnt/storage/iscsi/raspberry4/x32/raspbian12/'),
        Run('sudo mkdir -p /mnt/storage/iscsi/raspberry4/x64/raspbian11'),
        Run('sudo cp -r /root/arms/iscsi/raspberry4/x64/raspbian11/* /mnt/storage/iscsi/raspberry4/x64/raspbian11/'),
        Run('sudo mkdir -p /mnt/storage/iscsi/raspberry4/x64/raspbian12'),
        Run('sudo cp -r /root/arms/iscsi/raspberry4/x64/raspbian12/* /mnt/storage/iscsi/raspberry4/x64/raspbian12/'),
        Run('sudo mkdir -p /mnt/storage/iscsi/raspberry5/x32/raspbian12'),
        Run('sudo cp -r /root/arms/iscsi/raspberry5/x32/raspbian12/* /mnt/storage/iscsi/raspberry5/x32/raspbian12/'),
        Run('sudo mkdir -p /mnt/storage/iscsi/raspberry5/x64/raspbian12'),
        Run('sudo cp -r /root/arms/iscsi/raspberry5/x64/raspbian12/* /mnt/storage/iscsi/raspberry5/x64/raspbian12/'),
        Run('sudo chown -R ft:ft /root/arms/iscsi'),
        InstallCommon(
            'root',
            'provisioning/arms/beg-ft002_storage_sizes/jetsonnano/x64/ubuntu18/max_size_percent.cfg',
            '/mnt/storage/iscsi/jetsonnano/x64/ubuntu18',
            ),
        InstallCommon(
            'root',
            'provisioning/arms/beg-ft002_storage_sizes/raspberry4/x32/raspbian10/max_size_percent.cfg',
            '/mnt/storage/iscsi/raspberry4/x32/raspbian10',
            ),
        InstallCommon(
            'root',
            'provisioning/arms/beg-ft002_storage_sizes/raspberry4/x32/raspbian11/max_size_percent.cfg',
            '/mnt/storage/iscsi/raspberry4/x32/raspbian11',
            ),
        InstallCommon(
            'root',
            'provisioning/arms/beg-ft002_storage_sizes/raspberry4/x32/raspbian12/max_size_percent.cfg',
            '/mnt/storage/iscsi/raspberry4/x32/raspbian12',
            ),
        InstallCommon(
            'root',
            'provisioning/arms/beg-ft002_storage_sizes/raspberry4/x64/raspbian11/max_size_percent.cfg',
            '/mnt/storage/iscsi/raspberry4/x64/raspbian11',
            ),
        InstallCommon(
            'root',
            'provisioning/arms/beg-ft002_storage_sizes/raspberry4/x64/raspbian12/max_size_percent.txt',
            '/mnt/storage/iscsi/raspberry4/x64/raspbian12',
            ),
        InstallCommon(
            'root',
            'provisioning/arms/beg-ft002_storage_sizes/raspberry5/x32/raspbian12/max_size_percent.txt',
            '/mnt/storage/iscsi/raspberry5/x32/raspbian12',
            ),
        InstallCommon(
            'root',
            'provisioning/arms/beg-ft002_storage_sizes/raspberry5/x64/raspbian12/max_size_percent.txt',
            '/mnt/storage/iscsi/raspberry5/x64/raspbian12',
            ),
        ])
