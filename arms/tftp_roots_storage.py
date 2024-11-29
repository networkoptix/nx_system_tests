# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from abc import ABCMeta
from abc import abstractmethod
from contextlib import AbstractContextManager
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO

from arms.tftp_server_interface import TFTPServerControl


class TFTPRoot(metaclass=ABCMeta):

    @abstractmethod
    def set_for(self, ip_address: str):
        pass

    @abstractmethod
    def created_file(self, name: str) -> AbstractContextManager[BinaryIO]:
        pass


class LocalTFTPRoot(TFTPRoot):

    def __init__(self, server: TFTPServerControl, path: Path):
        self._server = server
        self._path = path

    def set_for(self, ip_address: str):
        self._server.set_tftp_root_for(ip_address, self._path)

    @contextmanager
    def created_file(self, name: str):
        file_name = self._path / name.lstrip("/")
        file_name.parent.mkdir(parents=True, exist_ok=True)
        with file_name.open('wb') as fd:
            yield fd

    def __repr__(self):
        return f'<TFTP Root: {self._path}>'
