# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from abc import ABCMeta
from abc import abstractmethod
from ipaddress import IPv4Address
from pathlib import Path
from typing import Iterator

_logger = logging.getLogger(__name__)


class EndpointsRegistry(metaclass=ABCMeta):

    @abstractmethod
    def find_root_path(self, ip: str) -> Path:
        pass


class FileEndpointsRegistry(EndpointsRegistry):

    def __init__(self, config_path: Path):
        self._config_path = config_path

    def _iter_configs(self) -> Iterator[tuple[IPv4Address, Path]]:
        for file in self._config_path.iterdir():
            try:
                ip_address = IPv4Address(file.name)
            except ValueError:
                _logger.debug("Ignore unparseable %s", file)
                continue
            try:
                path = _read_path(file)
            except FileNotFoundError:
                _logger.warning("%s is found but got removed shortly after", file)
                continue
            _logger.debug("Found path %s for ip %s", path, ip_address)
            yield ip_address, path

    def find_root_path(self, ip: str) -> Path:
        requested_ip = IPv4Address(ip)
        for configured_ip, path in self._iter_configs():
            if requested_ip == configured_ip:
                return path
        raise TFTPPathNotFound(f"Can't find a path for ip {ip}")


def _read_path(config_file: Path) -> Path:
    with config_file.open('r') as rd:
        raw_path = rd.readline()
    return Path(raw_path.strip()).expanduser()


class TFTPPathNotFound(Exception):
    pass
