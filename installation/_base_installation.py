# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from abc import ABCMeta
from abc import abstractmethod
from functools import lru_cache
from typing import Tuple

from distrib import BuildInfo
from distrib import Customization
from distrib import PathBuildInfo
from distrib import Version
from os_access import OsAccess
from os_access import RemotePath

_logger = logging.getLogger(__name__)


class _NotInstalled(Exception):
    pass


class CannotInstall(Exception):
    pass


class BaseInstallation(metaclass=ABCMeta):

    def __init__(self, os_access: OsAccess, dir: RemotePath):
        self.os_access = os_access
        self.dir = dir
        self._build_info_file = self.dir / 'build_info.txt'

    def __repr__(self):
        return f'<{self.__class__.__name__} on {self.os_access!r}>'

    @abstractmethod
    def install(self, installer: RemotePath):
        pass

    @abstractmethod
    def uninstall_all(self):
        pass

    @abstractmethod
    def get_binary_path(self) -> RemotePath:
        pass

    @abstractmethod
    def is_valid(self):
        pass

    @lru_cache()
    def _build_info(self) -> BuildInfo:
        try:
            return PathBuildInfo(self._build_info_file)
        except FileNotFoundError as e:
            raise _NotInstalled(e)

    def get_version(self) -> Version:
        return self._build_info().version()

    def older_than(self, branch: str) -> bool:
        installation_version = self.get_version()
        branch_version = self._branch_as_tuple(branch)
        return installation_version[:len(branch_version)] < branch_version

    def newer_than(self, branch: str) -> bool:
        installation_version = self.get_version()
        branch_version = self._branch_as_tuple(branch)
        return installation_version[:len(branch_version)] > branch_version

    @staticmethod
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

    def _customization(self) -> Customization:
        return self._build_info().customization()


class OsNotSupported(Exception):

    def __init__(self, installation_cls, os_access):
        super(OsNotSupported, self).__init__(
            "{!r} is not supported on {!r}.".format(
                installation_cls, os_access))
