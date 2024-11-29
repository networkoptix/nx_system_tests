# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from abc import ABCMeta
from abc import abstractmethod


class ARMRemoteControl(metaclass=ABCMeta):

    @abstractmethod
    async def shutdown(self):
        pass
