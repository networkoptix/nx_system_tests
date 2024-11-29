# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from abc import ABCMeta
from abc import abstractmethod
from pathlib import Path


class PrerequisiteStore(metaclass=ABCMeta):
    """Provide on-demand access to files located in network or locally."""

    @abstractmethod
    def fetch(self, relative_path: str) -> Path:
        pass

    @abstractmethod
    def url(self, relative_path: str) -> str:
        pass

    @abstractmethod
    def hostname(self):
        pass
