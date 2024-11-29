# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from abc import ABCMeta
from abc import abstractmethod


class PowerControlInterface(metaclass=ABCMeta):

    @abstractmethod
    async def power_on(self):
        pass

    @abstractmethod
    async def power_off(self):
        pass
