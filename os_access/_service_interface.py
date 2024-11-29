# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from abc import ABCMeta
from abc import abstractmethod
from typing import NamedTuple
from typing import Optional
from typing import Sequence


class ServiceManager:

    @abstractmethod
    def service(self, name) -> 'Service':
        pass

    @abstractmethod
    def dummy_service(self) -> 'Service':
        pass


class Service(metaclass=ABCMeta):

    @abstractmethod
    def get_username(self) -> str:
        pass

    @abstractmethod
    def start(self, timeout_sec: Optional[float] = None):
        pass

    @abstractmethod
    def stop(self, timeout_sec: Optional[float] = None):
        pass

    @abstractmethod
    def status(self) -> 'ServiceStatus':
        pass

    @abstractmethod
    def create(self, command: Sequence[str]):
        pass

    def is_running(self):
        """Shortcut."""
        return self.status().is_running

    def is_stopped(self):
        """Shortcut."""
        return self.status().is_stopped


class ServiceStatus(NamedTuple):

    is_running: bool
    is_stopped: bool
    pid: int  # 0 means no process in POSIX and Windows.


class ServiceStartError(Exception):
    pass
