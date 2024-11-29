# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from abc import ABCMeta
from abc import abstractmethod
from pathlib import Path


class TFTPServerControl(metaclass=ABCMeta):

    @abstractmethod
    def set_tftp_root_for(self, ip_address: str, tftp_root: Path):
        pass
