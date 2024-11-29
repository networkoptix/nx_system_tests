# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import zipfile
from abc import ABCMeta
from abc import abstractmethod
from pathlib import Path
from typing import Collection
from typing import Optional

from directories import get_ft_artifacts_root
from directories.prerequisites import PrerequisiteStore
from directories.prerequisites import make_prerequisite_store
from distrib import Distrib
from distrib import InstallerComponent
from distrib import InstallerKey
from distrib import InstallerName
from distrib import InstallerOs
from installation._arch import _arch_aliases
from installation._updates import LocalUpdateArchive
from mediaserver_scenarios.prerequisite_upload import DirectUploadSupplier
from mediaserver_scenarios.prerequisite_upload import Supplier
from os_access import OsAccess
from os_access import RemotePath

_logger = logging.getLogger(__name__)


class InstallerSupplier(metaclass=ABCMeta):

    def __init__(self, warehouse: PrerequisiteStore, distrib: Distrib, supplier: Supplier):
        self._warehouse = warehouse
        self._supplier = supplier
        self._distrib = distrib

    def __repr__(self):
        return f"InstallerSupplier({self._warehouse!r}, {self._distrib}, {self._supplier!r})"

    def distrib(self) -> Distrib:
        return self._distrib

    @abstractmethod
    def update_supplier(self) -> 'InstallerSupplier':
        pass

    def _package_name(self, package_type, os_access) -> InstallerName:
        arch = _arch_aliases[os_access.arch()]
        family = InstallerOs[os_access.OS_FAMILY]
        key = InstallerKey(package_type, family, arch)
        return self._distrib.installer_name(key)

    def upload_server_installer(self, os_access: OsAccess) -> RemotePath:
        name = self._package_name(InstallerComponent.server, os_access)
        return self._supplier.upload_to_remote(name.full_name, os_access)

    def upload_client_installer(self, os_access: OsAccess) -> RemotePath:
        name = self._package_name(InstallerComponent.client, os_access)
        return self._supplier.upload_to_remote(name.full_name, os_access)

    def upload_bundle_installer(self, os_access: OsAccess) -> RemotePath:
        name = self._package_name(InstallerComponent.bundle, os_access)
        return self._supplier.upload_to_remote(name.full_name, os_access)

    def upload_benchmark(self, os_access: OsAccess) -> RemotePath:
        name = self._package_name(InstallerComponent.vms_benchmark, os_access)
        return self._supplier.upload_to_remote(name.full_name, os_access)

    def upload_metadata_sdk(self, os_access: OsAccess):
        name = self._distrib.metadata_sdk_name()
        return self._supplier.upload_to_remote(name.full_name, os_access)

    def fetch_server_updates(self, platforms: Optional[Collection[str]] = None):
        return LocalUpdateArchive(self.distrib().installer_set(), self._warehouse, platforms)

    def static_web_content(self):
        web_admin_name = self.distrib().installer_set().web_admin()
        web_admin_path = self._warehouse.fetch(web_admin_name.full_name)
        return _StaticWebContent(web_admin_path)

    def upload_mobile_client(self, os_access: OsAccess):
        name = self._package_name(InstallerComponent.mobile_client, os_access)
        return self._supplier.upload_to_remote(name.full_name, os_access)


class ClassicInstallerSupplier(InstallerSupplier):

    def __init__(self, url: str):
        self._url = url
        store = make_prerequisite_store(url, get_ft_artifacts_root() / 'vms-installers')
        distrib = Distrib(url)
        super().__init__(store, distrib, DirectUploadSupplier(store))

    def __repr__(self):
        return f'ClassicInstallerSupplier({self._url})'

    def update_supplier(self) -> 'InstallerSupplier':
        return ClassicInstallerSupplier(self.distrib().updates_url())


class _StaticWebContent:

    def __init__(self, path: Path):
        self.path = path
        with zipfile.ZipFile(path) as web_admin_zip:
            version_file_info = web_admin_zip.getinfo('static/version.txt')
            with web_admin_zip.open(version_file_info.filename) as version_file:
                version_content = version_file.read().decode('utf-8')
        self.details = {}
        for line in version_content.splitlines():
            k, v = line.split(': ', maxsplit=1)
            self.details[k] = v
