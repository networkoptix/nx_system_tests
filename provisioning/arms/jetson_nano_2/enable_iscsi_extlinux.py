# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from provisioning import InstallCommon
from provisioning import Run
from provisioning.fleet import beg_ft002

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    beg_ft002.run([
        Run('scp /mnt/storage/tftp/jetsonnano/x64/ubuntu18/Image-4.9.337-tegra210 root@10.1.0.50/boot/'),
        Run('scp /mnt/storage/tftp/jetsonnano/x64/ubuntu18/initrd-4.9.337-tegra210 root@10.1.0.50/boot/'),
        InstallCommon('root', 'provisioning/arms/jetson_nano_2/extlinux.conf', '/boot/extlinux/'),
        ])
