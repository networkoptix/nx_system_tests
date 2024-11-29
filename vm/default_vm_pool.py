# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from functools import lru_cache
from pathlib import Path

from vm.nxwitness_snapshots.lib import PrebuiltSnapshotStrategy
from vm.virtual_box import VBoxAccessSettings
from vm.virtual_box import VBoxLinux
from vm.virtual_box import VBoxWindows
from vm.virtual_box._vboxmanage import get_virtual_box

vm_types = {
    'ubuntu16': VBoxLinux(
        name='ubuntu16',
        ram_mb=1024, cpu_count=1, access_settings=VBoxAccessSettings({
            'tcp': {1: 7001, 2: 22, 3: 7012, 4: 445},
            'udp': {5: 5353},
            })),
    'ubuntu18': VBoxLinux(
        name='ubuntu18',
        ram_mb=1024, cpu_count=1, access_settings=VBoxAccessSettings({
            'tcp': {1: 7001, 2: 22, 3: 7012, 4: 445},
            'udp': {5: 5353},
            })),
    'ubuntu20': VBoxLinux(
        name='ubuntu20',
        ram_mb=1024,
        cpu_count=2,  # See: https://bugs.launchpad.net/ubuntu/+source/linux/+bug/2022097
        access_settings=VBoxAccessSettings({
            'tcp': {1: 7001, 2: 22, 3: 7012, 4: 445},
            'udp': {5: 5353},
            })),
    'win10': VBoxWindows(
        name='win10',
        ram_mb=4096, cpu_count=4, access_settings=VBoxAccessSettings({
            'tcp': {1: 7001, 5: 5985, 9: 139, 4: 445, 3: 3389},
            'udp': {7: 137, 3: 5353},
            })),
    'win11': VBoxWindows(
        name='win11',
        ram_mb=4096, cpu_count=4, access_settings=VBoxAccessSettings({
            'tcp': {1: 7001, 5: 5985, 9: 139, 4: 445, 3: 3389},
            'udp': {7: 137, 3: 5353},
            })),
    'ubuntu22': VBoxLinux(
        name='ubuntu22',
        ram_mb=1024, cpu_count=1, access_settings=VBoxAccessSettings({
            'tcp': {1: 7001, 2: 22, 3: 7012, 4: 445},
            'udp': {5: 5353},
            })),
    'ubuntu24': VBoxLinux(
        name='ubuntu24',
        ram_mb=1024, cpu_count=1, access_settings=VBoxAccessSettings({
            'tcp': {1: 7001, 2: 22, 3: 7012, 4: 445},
            'udp': {5: 5353},
            })),
    'win2019': VBoxWindows(
        name='win2019',
        ram_mb=4096, cpu_count=4, access_settings=VBoxAccessSettings({
            'tcp': {1: 7001, 5: 5985, 9: 139, 4: 445, 3: 3389},
            'udp': {7: 137, 3: 5353},
            })),
    'statserver': VBoxLinux(
        name='statserver',
        ram_mb=2048, cpu_count=1, access_settings=VBoxAccessSettings({
            'tcp': {1: 8008, 2: 22},
            })),
    'chrome': VBoxLinux(
        name='chrome',
        ram_mb=2048,
        # Those VM have multiple CPU-bound processes inside a VM:
        # X server (Xvfb), VLC, ChromeDriver, multiple Chrome threads
        # These processes combined produce ~0.5 1m Load Average what makes Chrome quite sluggish.
        # Increasing CPU count further makes Chrome behave faster but sometimes unstable if running
        # on SC hosts.
        cpu_count=4,
        access_settings=VBoxAccessSettings({
            'tcp': {1: 22, 2: 9515, 3: 12312},
            })),
    'openldap': VBoxLinux(
        name='openldap',
        ram_mb=1024, cpu_count=1, access_settings=VBoxAccessSettings({
            'tcp': {1: 22, 2: 389, 3: 636},
            })),
    'active_directory': VBoxWindows(
        name='active_directory',
        ram_mb=4096, cpu_count=4, access_settings=VBoxAccessSettings({
            'tcp': {1: 5985, 2: 139, 3: 445, 4: 3389, 5: 389, 6: 636},
            })),
    }


@lru_cache()
def public_default_vm_pool(artifact_dir: Path) -> PrebuiltSnapshotStrategy:
    hypervisor = get_virtual_box()
    return PrebuiltSnapshotStrategy(hypervisor, artifact_dir)
