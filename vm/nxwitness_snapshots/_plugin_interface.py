# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from abc import ABCMeta
from abc import abstractmethod
from pathlib import Path

from distrib import BuildRecord
from distrib import Distrib
from os_access import OsAccess


class SnapshotPlugin(metaclass=ABCMeta):
    _distrib: Distrib

    @abstractmethod
    def name_prefix(self, os_name: str) -> str:
        pass

    def build_record(self) -> BuildRecord:
        return BuildRecord(self._distrib.tags_raw())

    @abstractmethod
    def prepare(self, os_access: OsAccess, artifacts_dir: Path):
        pass
