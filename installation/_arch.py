# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from distrib import InstallerArch

_arch_aliases = {
    'x86_64': InstallerArch.x64,
    '64-bit': InstallerArch.x64,
    'arm_32': InstallerArch.arm32,  # noqa SpellCheckingInspection
    'arm_64': InstallerArch.arm64,  # noqa SpellCheckingInspection
    'm1': InstallerArch.arm64,
    }
