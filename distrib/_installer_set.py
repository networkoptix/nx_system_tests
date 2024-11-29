# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
"""Parsed group of distrib packages.

>>> installer_set = InstallerSet([
...     'nxwitness-metadata_sdk-4.3.0.968-universal-private.zip',
...     'nxwitness-client_debug-4.3.0.968-windows_x64-private-test.zip',
...     ])
>>> installer_set.metadata_sdk().full_name
'nxwitness-metadata_sdk-4.3.0.968-universal-private.zip'

>>> from distrib import LINUX_BENCHMARK
>>> from distrib import LINUX_SERVER_ARM64
>>> from distrib import WINDOWS_SERVER
>>> installer_set = InstallerSet([
...     'nxwitness-server-0.0.0.0000-linux_arm64-local.deb',
...     'nxwitness-client-0.0.0.0000-windows_x64-local-unsigned.exe',
...     'nxwitness-vms_benchmark-0.0.0.0000-linux_x64-local.zip',
...     ])
>>> installer_set.has_installers(LINUX_SERVER_ARM64, LINUX_BENCHMARK)
True
>>> installer_set.has_installers(WINDOWS_SERVER)
False

>>> installer_set = InstallerSet([
...     'nxwitness-server-6.1.0.12345-linux_arm64-local.deb',
...     'nxwitness-mobile_client-24.1.3.12345-windows_x64-local.zip',
...     ])
>>> installer_set.version
Version('6.1.0.12345')
>>> installer_set = InstallerSet([
...     'nxwitness-server-6.1.0.12345-linux_arm64-local.deb',
...     'nxwitness-mobile_client-24.1.3.12345-windows_x64-local.zip',
...     'nxwitness-mobile_client-24.1.3.54321-windows_x64-local.zip',
...     ])
Traceback (most recent call last):
...
RuntimeError: Expected no mobile installers or single version, found: {Version('24.1.3.54321'), Version('24.1.3.12345')}
"""
from __future__ import annotations

import logging
from typing import Collection
from typing import Sequence

from distrib._customizations import Customization
from distrib._installer_name import InstallerComponent
from distrib._installer_name import InstallerKey
from distrib._installer_name import InstallerName
from distrib._installer_name import PackageNameParseError
from distrib._version import Version

_logger = logging.getLogger(__name__)


class InstallerNotFound(Exception):
    pass


class InstallerSet:

    version: Version
    customization: Customization

    def __init__(self, file_names: Collection[str]):
        _logger.debug("Search for packages among: %r", file_names)
        self._file_names = []
        self._installer_names = []
        for name in file_names:
            try:
                installer = InstallerName(name)
            except PackageNameParseError as e:
                _logger.debug("File %s: %s", name, e)
                continue
            _logger.info("File %r", installer)
            self._installer_names.append(installer)
            self._file_names.append(name)
        if not self._installer_names:
            raise RuntimeError(f"No installers among: {file_names!r}")
        customizations = {name.customization for name in self._installer_names}
        _logger.debug("Customizations: %r", customizations)
        try:
            [self.customization] = customizations
        except ValueError:
            raise RuntimeError(
                f"Expected installers of single customization, found: {customizations!r}")
        version_categories = {
            InstallerComponent.mobile_client: 'mobile',
            InstallerComponent.server: 'main',
            InstallerComponent.client: 'main',
            InstallerComponent.server_debug: 'main',
            InstallerComponent.client_debug: 'main',
            InstallerComponent.vms_benchmark: 'main',
            InstallerComponent.bundle: 'main',
            InstallerComponent.client_update: 'main',
            InstallerComponent.cloud_storage_sdk: 'main',
            InstallerComponent.libs_debug: 'main',
            InstallerComponent.metadata_sdk: 'main',
            InstallerComponent.misc_debug: 'main',
            InstallerComponent.server_update: 'main',
            InstallerComponent.storage_sdk: 'main',
            InstallerComponent.testcamera: 'main',
            InstallerComponent.video_source_sdk: 'main',
            InstallerComponent.webadmin: 'main',
            InstallerComponent.cloud_debug: 'main',
            InstallerComponent.paxton_plugin: 'main',
            InstallerComponent.unit_tests: 'main',
            }
        versions = {
            name.version
            for name in self._installer_names
            if version_categories[name.component] == 'main'
            }
        _logger.debug("Versions: %r", versions)
        try:
            [self.version] = versions
        except ValueError:
            raise RuntimeError(
                f"Expected installers of single version, found: {versions!r}")
        mobile_versions = {
            name.version
            for name in self._installer_names
            if version_categories[name.component] == 'mobile'
            }
        _logger.debug("Mobile client versions: %r", mobile_versions)
        if len(mobile_versions) > 1:
            raise RuntimeError(
                f"Expected no mobile installers or single version, found: {mobile_versions!r}")

    def __repr__(self):
        return f'{self.__class__.__name__}({self._file_names!r})'

    def all_names(self) -> Collection[InstallerName]:
        return self._installer_names

    def installer_name(self, key: InstallerKey) -> InstallerName:
        platform = '{}_{}'.format(key.os_name.value, key.arch.value)
        for name in self._installer_names:
            if name.component != key.component:
                _logger.debug("Not a %s but a %s: %s", key.component, name.component, name)
                continue
            if name.platform != platform:
                _logger.debug("Not for %s but for %s: %s", platform, name.platform, name)
                continue
            _logger.debug("Found %s for %s: %s", key.component, platform, name)
            return name
        raise InstallerNotFound(
            f"Cannot find {key.component} for {platform}; "
            f"make sure it was built and published; "
            f"check the installers directory URL; "
            f"available installers: "
            f"{', '.join(i.full_name for i in self._installer_names)}")

    def has_installers(self, *installer_keys: InstallerKey) -> bool:
        for requested_installer_key in installer_keys:
            for installer_name in self._installer_names:
                if requested_installer_key == installer_name.key():
                    break
            else:
                return False
        return True

    def metadata_sdk(self) -> InstallerName:
        for name in self._installer_names:
            if name.component == InstallerComponent.metadata_sdk:
                break
        else:
            raise InstallerNotFound(f"Metadata SDK not found among: {self}")
        if name.platform != 'universal':
            raise RuntimeError(f"Metadata SDK platform is not 'universal' but {name.platform!r}")
        return name

    def update_names(self) -> Sequence[InstallerName]:
        return [
            name
            for name in self._installer_names
            if name.component == InstallerComponent.server_update
            ]

    def web_admin(self) -> InstallerName:
        for name in self._installer_names:
            if name.component == InstallerComponent.webadmin:
                return name
        raise InstallerNotFound(f"WebAdmin not found among: {self}")
