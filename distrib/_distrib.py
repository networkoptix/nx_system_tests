# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import re
from typing import Collection
from typing import Tuple
from urllib.error import HTTPError
from urllib.error import URLError
from urllib.request import urlopen

from distrib._build_info import DistribUrlBuildInfo
from distrib._ci_info import _CIInfo
from distrib._ci_info import _UpdatesUrlEmpty
from distrib._customizations import Customization
from distrib._installer_name import InstallerKey
from distrib._installer_name import InstallerName
from distrib._installer_name import LINUX_CLIENT
from distrib._installer_name import LINUX_SERVER
from distrib._installer_name import WINDOWS_BUNDLE
from distrib._installer_name import WINDOWS_CLIENT
from distrib._installer_name import WINDOWS_SERVER
from distrib._installer_set import InstallerSet
from distrib._link_parser import parse_links
from distrib._specific_features import SpecificFeatures
from distrib._url_packer import compress_url
from distrib._version import Version

_logger = logging.getLogger(__name__)


class _RawDistrib:

    def __init__(
            self,
            distrib_url: str,
            distrib_files: Collection[str],
            build_info: bytes,
            ci_info: bytes,
            specific_features: bytes,
            ):
        self._url = distrib_url.rstrip('/') + '/'
        self._build_info_raw = build_info
        self._ci_info_raw = ci_info
        self._specific_features_raw = specific_features
        self._installer_set = InstallerSet(distrib_files)

    def url(self) -> str:
        return self._url

    def can_be_updated_to(self, other: '_RawDistrib') -> bool:
        if other._installer_set.customization != self._installer_set.customization:
            return False
        if other._installer_set.version <= self._installer_set.version:
            return False
        return True

    def assert_not_older_than(self, branch: str, err_msg: str = None):
        if self.older_than(branch):
            if err_msg is None:
                err_msg = f"Branch {branch} and older are not supported"
            raise BranchNotSupported(err_msg)

    def older_than(self, branch: str) -> bool:
        installer_version = self._installer_set.version
        branch_version = _branch_as_tuple(branch)
        return installer_version[:len(branch_version)] < branch_version

    def newer_than(self, branch: str) -> bool:
        installer_version = self._installer_set.version
        branch_version = _branch_as_tuple(branch)
        return installer_version[:len(branch_version)] > branch_version

    def equals(self, branch: str) -> bool:
        installer_version = self._installer_set.version
        branch_version = _branch_as_tuple(branch)
        return installer_version[:len(branch_version)] == branch_version

    def assert_api_support(self, api_version: str, group: str = 'any') -> None:
        if re.fullmatch(r'v\d+(plus)?', api_version) is None:
            raise ValueError(f"Invalid API version: {api_version!r}")
        if api_version == 'v2':
            if self.older_than('vms_5.1'):
                raise APITooNewForThisVersion(
                    f"API {api_version} does not work with {self}")
        if api_version == 'v3':
            if self.older_than('vms_6.0'):
                raise APITooNewForThisVersion(
                    f"API {api_version} does not work with {self}")
        if api_version == 'v4':
            if self.older_than('vms_6.1'):
                raise APITooNewForThisVersion(
                    f"API {api_version} does not work with {self}")
        if group == 'users':
            if api_version == 'v0':
                if not self.older_than('vms_6.0'):
                    raise APIDeprecated(
                        "Old API endpoints such as ec2/getUserRoles, "
                        "ec2/saveUserRole and ec2/removeUserRole "
                        "are not supported since version 6.0")
        if group == 'ldap_parameters':
            if not self.older_than('vms_6.0'):
                if api_version in ('v0', 'v1', 'v2'):
                    raise APIDeprecated(
                        "After VMS-31378, API versions 0..2 cannot be used "
                        "to set LDAP parameters")

    def assert_os_support(self, os_name: str) -> None:
        # Release builds do not have specific_features.txt.
        # See: https://artifactory.us.nxteam.dev/artifactory/release-vms/default/5.1.0.37133/
        # If specific features are empty - assume OS is supported.
        if not self._specific_features_raw:
            return
        key = 'supports_' + os_name
        level = self.specific_features().get(key, 0)
        if level <= 0:
            raise OSNotSupported(f"{os_name} is not supported in {self}")

    def assert_branch_not_mobile(self):
        if self._branch().startswith('mobile_'):
            raise BranchNotSupported("mobile_ branches are not supported")

    def _branch(self):
        return DistribUrlBuildInfo(self.url()).branch()

    def version(self) -> Version:
        return self._installer_set.version

    def customization(self) -> Customization:
        return self._installer_set.customization

    def installer_set(self) -> InstallerSet:
        return self._installer_set

    def assert_specific_feature(self, name: str, value: int = 1):
        if self.specific_features().get(name) < value:
            raise SpecificFeatureNotSupported(
                f"Specific feature {name} with value '{value!r}' not supported")

    def assert_specific_feature_not_higher_than(self, name: str, value: int):
        if self.specific_features().get(name) > value:
            raise SpecificFeatureNotSupported(
                f"Specific feature {name} is higher than '{value!r}'")

    def specific_features(self) -> SpecificFeatures:
        return SpecificFeatures(self._specific_features_raw)

    def installer_name(self, key: InstallerKey):
        return self._installer_set.installer_name(key)

    def metadata_sdk_name(self) -> InstallerName:
        return self._installer_set.metadata_sdk()

    def _get_server_installer_name(self, os_name: str) -> str:
        if os_name.startswith('ubuntu'):
            installer_key = LINUX_SERVER
        elif os_name.startswith('win'):
            installer_key = WINDOWS_SERVER
        else:
            raise OSNotSupported(f"{os_name} is not supported in {self}")
        installer_name = self.installer_name(installer_key)
        return installer_name.full_name

    def _get_client_installer_name(self, os_name: str) -> str:
        if os_name.startswith('ubuntu'):
            installer_key = LINUX_CLIENT
        elif os_name.startswith('win'):
            installer_key = WINDOWS_CLIENT
        else:
            raise OSNotSupported(f"{os_name} is not supported in {self}")
        installer_name = self.installer_name(installer_key)
        return installer_name.full_name

    def _get_bundle_installer_name(self, os_name: str) -> str:
        if os_name.startswith('win'):
            installer_key = WINDOWS_BUNDLE
        else:
            raise OSNotSupported(f"{os_name} is not supported in {self}")
        installer_name = self.installer_name(installer_key)
        return installer_name.full_name

    def server_dependent_prefix(self, os_name):
        installer_file_name = self._get_server_installer_name(os_name)
        compressed_url = compress_url(self.url())
        prefix = '--'.join([installer_file_name, compressed_url])
        return prefix

    def client_dependent_prefix(self, os_name):
        installer_file_name = self._get_client_installer_name(os_name)
        compressed_url = compress_url(self.url())
        prefix = '--'.join([installer_file_name, compressed_url])
        return prefix

    def bundle_dependent_prefix(self, os_name):
        installer_file_name = self._get_bundle_installer_name(os_name)
        compressed_url = compress_url(self.url())
        prefix = '--'.join([installer_file_name, compressed_url])
        return prefix

    def updates_url(self) -> str:
        if not self._ci_info_raw:
            raise RuntimeError("File ci_info.txt is missing; can't get updates URL")
        ci_info = _CIInfo(self._ci_info_raw)
        return ci_info.updates_url()

    def assert_updates_support(self, err_msg: str):
        try:
            self.updates_url()
        except _UpdatesUrlEmpty:
            if '/build-vms-release/' in self._url:
                raise UpdatesNotSupported(err_msg)
            else:
                raise

    def assert_can_update_to(self, new_version: Version):
        [*update_version, _] = new_version
        [*actual_version, _] = self.version()
        if actual_version >= update_version:
            actual_version_str = '.'.join([str(number) for number in actual_version])
            new_version_str = '.'.join([str(number) for number in update_version])
            raise UpdatesNotSupported(
                f"Version {actual_version_str} cannot be updated to version {new_version_str}")

    def tags_raw(self) -> str:
        tag_sources = [
            self._build_info_raw,
            self._specific_features_raw,
            self._ci_info_raw,
            ]
        raw_metadata = ''.join(f"{tags_raw.decode()}\n\n" for tags_raw in tag_sources)
        return f"{raw_metadata}\nft:url={self.url()}"

    def latest_api_version(self, min_version: str) -> str:
        if self.older_than('vms_6.0'):
            if min_version > 'v2':
                raise BranchNotSupported(f"{self._installer_set.version} only supports APIv2 and older")
            return 'v2'
        elif self.older_than('vms_6.1'):
            if min_version > 'v3':
                raise BranchNotSupported(f"{self._installer_set.version} only supports APIv3 and older")
            return 'v3'
        else:
            if min_version > 'v4':
                raise BranchNotSupported(f"{self._installer_set.version} only supports APIv4 and older")
            return 'v4'


class Distrib(_RawDistrib):

    def __init__(self, url: str):
        url = url.rstrip('/')
        try:
            distrib_files = _list(url)
        except URLError as e:
            raise RuntimeError(
                "Installers not found or inaccessible, "
                "use new installers as old builds are periodically deleted, "
                "check credentials, access rights and domain name: "
                f"{e}")
        super().__init__(
            url,
            distrib_files,
            _read_or_empty(url + '/build_info.txt'),
            _read_or_empty(url + '/ci_info.txt'),
            _read_or_empty(url + '/specific_features.txt'),
            )

    def __repr__(self):
        return f'{self.__class__.__name__}({self._url!r})'


def _read_or_empty(url: str) -> bytes:
    try:
        response = urlopen(url, timeout=10)
    except HTTPError as e:
        if e.code != 404:
            raise
        result = b''
    else:
        result = response.read()
    return result


def _list(url: str) -> Collection[str]:
    response = urlopen(url, timeout=10)
    all_links = parse_links(response.url, response)
    names = []
    for link in all_links:
        if not link.startswith(url):
            _logger.debug("Skip: Not within root URL: %s", link)
            continue
        if link.endswith('/'):
            _logger.debug("Skip: Not a file URL: %s", link)
            continue
        path = link[len(url):].lstrip('/')
        if '/' in path:
            _logger.debug("Skip: In a subdir: %s", link)
            continue
        _logger.debug("Take: File %s from: %s", path, link)
        names.append(path)
    return names


class OSNotSupported(Exception):
    pass


class APINotSupported(Exception):
    pass


class APIDeprecated(APINotSupported):
    pass


class APITooNewForThisVersion(APINotSupported):
    pass


class BranchNotSupported(Exception):
    pass


class SpecificFeatureNotSupported(Exception):
    pass


class UpdatesNotSupported(Exception):
    pass


def _branch_as_tuple(name: str) -> Tuple:
    prefix = 'vms_'
    if not name.startswith(prefix):
        raise RuntimeError('Only vms_* branches are supported')
    try:
        version = tuple(int(v) for v in name[len('vms_'):].split('.', 3))
    except ValueError:
        raise RuntimeError(f'Unexpected branch name: {name}')
    if len(version) < 2:
        raise RuntimeError("Branch must contain at least major and minor version numbers")
    return version
