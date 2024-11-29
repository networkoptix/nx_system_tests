# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from abc import ABC
from abc import abstractmethod


class Q(ABC):

    @abstractmethod
    def q(self):
        pass
