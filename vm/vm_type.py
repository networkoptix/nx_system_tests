# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from abc import ABCMeta
from abc import abstractmethod
from contextlib import AbstractContextManager
from typing import Optional

from vm.vm import VM

_logger = logging.getLogger(__name__)


class VMSnapshotTemplate(metaclass=ABCMeta):

    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def vm_locked(self, snapshot_uri: str, parent_uri: Optional[str] = None) -> AbstractContextManager[VM]:
        pass
