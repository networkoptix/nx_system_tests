# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import socket
import time
from abc import ABCMeta
from abc import abstractmethod
from ipaddress import ip_address
from typing import Mapping
from typing import Union
from urllib.parse import urlparse

_logger = logging.getLogger(__name__)


class LicenseServer(metaclass=ABCMeta):

    @abstractmethod
    def url(self) -> str:
        pass

    @abstractmethod
    def generate(self, license_data: Mapping[str, Union[str, float]]) -> str:
        pass

    @abstractmethod
    def activate(self, license_key: str, hardware_id: str) -> str:
        pass

    @abstractmethod
    def deactivate(self, license_key: str):
        pass

    @abstractmethod
    def disable(self, license_key: str):
        pass

    @abstractmethod
    def info(self, license_key: str):
        pass


class _LicenseServerUrl:

    def __init__(self, url: str):
        self._parsed_url = urlparse(url)
        self.host = self._parsed_url.hostname
        assert self.host
        self.port = self._parsed_url.port or 443
        try:
            server_ip_address = ip_address(self.host)
        except ValueError:
            server_ip_address = _get_host_by_name(self.host)
        self.ip_address = str(server_ip_address)


def _get_host_by_name(hostname):
    for _ in range(3):
        try:
            return socket.gethostbyname(hostname)
        except socket.gaierror:
            _logger.debug("Failed to get ip by name {}".format(hostname))
            time.sleep(1)
    return socket.gethostbyname(hostname)
