# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import ctypes
import logging
import os
import socket
from ipaddress import IPv4Interface
from typing import Mapping
from typing import Sequence

_logger = logging.getLogger(__name__)


class SockaddrIn(ctypes.Structure):
    _fields_ = [
        ('sin_family', ctypes.c_uint16),
        ('sin_port', ctypes.c_uint16),
        ('sin_addr', ctypes.c_uint8 * 4),
        ('sin_zero', ctypes.c_uint8 * 8),
        ]


class Sockaddr(ctypes.Structure):
    _fields_ = [
        ('sa_family', ctypes.c_uint8),
        ('sa_data', ctypes.c_uint8 * 14),
        ]


class Ifaddrs(ctypes.Structure):
    pass


Ifaddrs._fields_ = [
    ('ifa_next', ctypes.POINTER(Ifaddrs)),
    ('ifa_name', ctypes.c_char_p),
    ('ifa_flags', ctypes.c_uint),
    ('ifa_addr', ctypes.POINTER(Sockaddr)),
    ('ifa_netmask', ctypes.POINTER(Sockaddr))]


_libc = ctypes.CDLL("libc.so.6")


def _getifaddrs_result() -> ctypes.POINTER:
    entry_pointer = ctypes.POINTER(Ifaddrs)()
    if _libc.getifaddrs(ctypes.byref(entry_pointer)) != 0:
        error_code = ctypes.get_errno()
        raise OSError(error_code, os.strerror(error_code))
    return entry_pointer


def get_local_ipv4_interfaces() -> Mapping[str, Sequence[IPv4Interface]]:
    _logger.debug("Request all host ip addresses ...")
    address_entry_pointer = _getifaddrs_result()
    result = {}
    while address_entry_pointer:
        entry = address_entry_pointer.contents
        address_entry_pointer = entry.ifa_next
        nic_name = entry.ifa_name.decode("ascii")
        if not entry.ifa_addr:
            _logger.debug("Entry for %s is skipped. Does not have any IP addresses", nic_name)
            continue
        if entry.ifa_addr.contents.sa_family != socket.AF_INET:
            _logger.debug("Entry for %s is skipped. It is not an IPv4 address", nic_name)
            continue
        address_ctype = ctypes.cast(entry.ifa_addr, ctypes.POINTER(SockaddrIn)).contents
        netmask_ctype = ctypes.cast(entry.ifa_netmask, ctypes.POINTER(SockaddrIn)).contents
        address_bytes = bytes(address_ctype.sin_addr)
        netmask_string = '.'.join(map(str, netmask_ctype.sin_addr))
        ipv4_interface = IPv4Interface((address_bytes, netmask_string))
        _logger.debug("Found a valid %s for nic %s", ipv4_interface, nic_name)
        result.setdefault(nic_name, []).append(ipv4_interface)
    return result
