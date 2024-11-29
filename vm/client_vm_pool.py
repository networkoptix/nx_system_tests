# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from vm.virtual_box import VBoxAccessSettings
from vm.virtual_box import VBoxWindows

vm_types = {
    'win10': VBoxWindows(
        name='win10',
        ram_mb=4096, cpu_count=4, access_settings=VBoxAccessSettings({
            'tcp': {1: 7001, 5: 5985, 9: 139, 4: 445, 3: 3389, 7: 7012, 8: 12312},
            'udp': {7: 137, 3: 5353},
            })),
    'win11': VBoxWindows(
        name='win11',
        ram_mb=4096, cpu_count=4, access_settings=VBoxAccessSettings({
            'tcp': {1: 7001, 5: 5985, 9: 139, 4: 445, 3: 3389, 7: 7012, 8: 12312},
            'udp': {7: 137, 3: 5353},
            })),
    }
