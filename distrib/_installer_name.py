# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
"""Parsed distrib package name.

>>> InstallerName('nxwitness-server-3.2.0.20805-linux64.deb')
InstallerName('nxwitness-server-3.2.0.20805-linux64.deb')
>>> InstallerName('nxwitness-server-4.0.0.2049-linux64-beta.deb')
InstallerName('nxwitness-server-4.0.0.2049-linux64-beta.deb')
>>> InstallerName('nxwitness-server-4.0.0.2049-linux64-demo.deb')
InstallerName('nxwitness-server-4.0.0.2049-linux64-demo.deb')
>>> InstallerName('nxwitness-server-4.0.0.2049-linux64-test.deb')
InstallerName('nxwitness-server-4.0.0.2049-linux64-test.deb')
>>> InstallerName('nxwitness-server-4.0.0.2049-win64-beta-test.exe')
InstallerName('nxwitness-server-4.0.0.2049-win64-beta-test.exe')
>>> InstallerName('nxwitness-server-3.2.0.2032-win64-beta-test.exe')
InstallerName('nxwitness-server-3.2.0.2032-win64-beta-test.exe')
>>> InstallerName('wave-server-3.2.0.40235-linux86-beta-test.zip')
InstallerName('wave-server-3.2.0.40235-linux86-beta-test.zip')
>>> InstallerName('dwspectrum-server-3.2.0.40235-linux86-beta-test.zip')
InstallerName('dwspectrum-server-3.2.0.40235-linux86-beta-test.zip')
>>> InstallerName('wave-server-3.2.0.40238-win86-beta-test.msi')
InstallerName('wave-server-3.2.0.40238-win86-beta-test.msi')
"""

from __future__ import annotations

import logging
import re
from enum import Enum
from typing import NamedTuple

from distrib._customizations import known_customizations
from distrib._version import Version

_logger = logging.getLogger(__name__)


class InstallerName:
    # Installer name regex.
    # See: https://networkoptix.atlassian.net/wiki/spaces/SD/pages/79462475/Installer+Filenames
    _name_re = re.compile(
        r'''
            ^ (?P<name> \w+ )
            - (?P<component> \w+ )
            - (?P<version> \d+\.\d+\.\d+\.\d+ )
            - (?P<platform> \w+ )
            (?: - (?P<publication_type> beta | private | rc | patch | private_patch | local ) )?
            (?: - (?P<cloud_group> test | tmp | dev | demo | stage | prod ) )?
            (?: - (?P<unsigned> unsigned ) )?
            # .apk and .ipa extensions are not supported by FT.
            (?P<extension> \. ( exe | msi | deb | zip | tar\.gz | dmg ) )
            $
        ''',
        re.VERBOSE)

    # Map platform names in file names and in update info (packages.json).
    # Update info style is used throughout the project as it's consistent.
    # linux_* actually is for Debian/Ubuntu: no other distros are supported
    # and if, for example, CentOS is supported, names will likely be changed.
    _platform_map = {
        'linux64': 'linux_x64',
        'win64': 'windows_x64',
        'mac': 'macos',
        'bpi': 'nx1',
        # Others are assumed to be same in update info and file name.
        }

    def __init__(self, name: str):
        m = self._name_re.match(name)
        if m is None:
            raise PackageNameParseError("Installer name not understood: {}".format(name))
        _logger.debug("Parsed name: %r", m.groupdict())
        self.full_name = name
        self.extension = m.group('extension')
        installer_name = m.group('name')
        for customization in known_customizations.values():
            if customization.installer_name == installer_name:
                self.customization = customization
                break
        else:
            raise PackageNameParseError("No customization found for {}".format(name))
        component = m.group('component')
        try:
            self.component = InstallerComponent(component)
        except ValueError:
            raise PackageNameParseError(
                f"{component} is not present in {InstallerComponent}")
        self.version = Version(m.group('version'))
        platform_part = m.group('platform')
        self.platform = self._platform_map.get(platform_part, platform_part)
        if self.platform in ['ios', 'android']:
            raise PackageNameParseError("Unsupported platform: {}".format(self.platform))
        self.publication_type = m.group('publication_type')
        self.cloud_group = m.group('cloud_group') or None
        self.is_unsigned = bool(m.group('unsigned'))

    def key(self) -> InstallerKey:
        try:
            _os, arch = self.platform.split("_")
        except ValueError:
            _os = self.platform
            arch = 'unspecified'
        return InstallerKey(self.component, InstallerOs(_os), InstallerArch(arch))

    def __repr__(self):
        return f"InstallerName({self.full_name!r})"


class InstallerOs(Enum):
    linux = 'linux'
    windows = 'windows'
    macos = 'macos'
    universal = 'universal'
    net2v5 = 'Net2v5'
    net2v6 = 'Net2v6'


class InstallerArch(Enum):
    x64 = 'x64'
    arm32 = 'arm32'
    arm64 = 'arm64'
    apple_m1 = 'm1'
    unspecified = 'unspecified'


class InstallerComponent(Enum):
    server = 'server'
    client = 'client'
    server_debug = 'server_debug'
    client_debug = 'client_debug'
    vms_benchmark = 'vms_benchmark'
    bundle = 'bundle'
    client_update = 'client_update'
    cloud_storage_sdk = 'cloud_storage_sdk'
    libs_debug = 'libs_debug'
    metadata_sdk = 'metadata_sdk'
    misc_debug = 'misc_debug'
    server_update = 'server_update'
    storage_sdk = 'storage_sdk'
    testcamera = 'testcamera'
    video_source_sdk = 'video_source_sdk'
    webadmin = 'webadmin'
    cloud_debug = 'cloud_debug'
    paxton_plugin = 'paxton_plugin'
    unit_tests = 'unit_tests'
    mobile_client = 'mobile_client'


class InstallerKey(NamedTuple):
    component: InstallerComponent
    os_name: InstallerOs
    arch: InstallerArch


WINDOWS_SERVER = InstallerKey(InstallerComponent.server, InstallerOs.windows, InstallerArch.x64)
WINDOWS_CLIENT = InstallerKey(InstallerComponent.client, InstallerOs.windows, InstallerArch.x64)
WINDOWS_BENCHMARK = InstallerKey(InstallerComponent.vms_benchmark, InstallerOs.windows, InstallerArch.x64)
WINDOWS_BUNDLE = InstallerKey(InstallerComponent.bundle, InstallerOs.windows, InstallerArch.x64)
MACOS_SERVER_ARM64 = InstallerKey(InstallerComponent.server, InstallerOs.macos, InstallerArch.arm64)
LINUX_SERVER = InstallerKey(InstallerComponent.server, InstallerOs.linux, InstallerArch.x64)
LINUX_SERVER_ARM64 = InstallerKey(InstallerComponent.server, InstallerOs.linux, InstallerArch.arm64)
LINUX_SERVER_ARM32 = InstallerKey(InstallerComponent.server, InstallerOs.linux, InstallerArch.arm32)
LINUX_CLIENT = InstallerKey(InstallerComponent.client, InstallerOs.linux, InstallerArch.x64)
LINUX_BENCHMARK = InstallerKey(InstallerComponent.vms_benchmark, InstallerOs.linux, InstallerArch.x64)


class PackageNameParseError(Exception):
    pass
