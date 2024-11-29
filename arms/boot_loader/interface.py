# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from abc import ABCMeta
from abc import abstractmethod

from arms.kernel_arguments import LinuxKernelArguments
from arms.tftp_roots_storage import TFTPRoot


class TFTPBootloader(metaclass=ABCMeta):

    @abstractmethod
    def apply(self, tftp_root: TFTPRoot, kernel_arguments: LinuxKernelArguments):
        pass
