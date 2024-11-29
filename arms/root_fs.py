# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from abc import ABCMeta
from abc import abstractmethod
from pathlib import Path

from arms.kernel_arguments import LinuxKernelArguments


class RemoteRootFS(metaclass=ABCMeta):

    @abstractmethod
    def get_arguments(self) -> LinuxKernelArguments:
        pass

    @abstractmethod
    async def detach_disk(self):
        pass

    @abstractmethod
    async def attach_disk(self, path: Path):
        pass

    @abstractmethod
    async def wait_disconnected(self):
        pass
