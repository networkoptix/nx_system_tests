# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import ctypes
import logging
import socket
from ctypes import wintypes
from ipaddress import IPv4Interface
from typing import Mapping
from typing import Sequence

_logger = logging.getLogger(__name__)

NO_ERROR = 0
ERROR_BUFFER_OVERFLOW = 111


class _IPv4Address(ctypes.Structure):
    _fields_ = [
        ('sin_family', ctypes.c_uint16),
        ('sin_port', ctypes.c_uint16),
        ('sin_addr', ctypes.c_uint8 * 4),
        ('sin_zero', ctypes.c_uint8 * 8)]

    def __index__(self):
        return int.from_bytes(self.sin_addr, byteorder="big", signed=False)


class SocketAddress(ctypes.Structure):
    _fields_ = [
        ('lpSockaddr', ctypes.POINTER(_IPv4Address)),
        ('iSockaddrLength', wintypes.INT)]


class _UnicastAddress(ctypes.Structure):
    pass


_UnicastAddress._fields_ = [
    ('Length', wintypes.ULONG),
    ('Flags', wintypes.DWORD),
    ('Next', ctypes.POINTER(_UnicastAddress)),
    ('Address', SocketAddress),
    ('PrefixOrigin', ctypes.c_uint),
    ('SuffixOrigin', ctypes.c_uint),
    ('DadState', ctypes.c_uint),
    ('ValidLifetime', wintypes.ULONG),
    ('PreferredLifetime', wintypes.ULONG),
    ('LeaseLifetime', wintypes.ULONG),
    ('OnLinkPrefixLength', ctypes.c_uint8)]


class _Adapter(ctypes.Structure):

    def interfaces_list(self) -> Sequence[IPv4Interface]:
        result = []
        address_pointer = self.FirstUnicastAddress
        while address_pointer:
            address = address_pointer.contents
            address_pointer = address.Next
            ipv4_address = address.Address.lpSockaddr.contents
            ipv4_interface = IPv4Interface((int(ipv4_address), address.OnLinkPrefixLength))
            _logger.debug("Found %s for nic %s", ipv4_interface, self.FriendlyName)
            result.append(ipv4_interface)
        return result


_Adapter._fields_ = [
    ('Length', wintypes.ULONG),
    ('IfIndex', wintypes.DWORD),
    ('Next', ctypes.POINTER(_Adapter)),
    ('AdapterName', ctypes.c_char_p),
    ('FirstUnicastAddress', ctypes.POINTER(_UnicastAddress)),
    ('FirstAnycastAddress', ctypes.POINTER(None)),
    ('FirstMulticastAddress', ctypes.POINTER(None)),
    ('FirstDnsServerAddress', ctypes.POINTER(None)),
    ('DnsSuffix', ctypes.c_wchar_p),
    ('Description', ctypes.c_wchar_p),
    ('FriendlyName', ctypes.c_wchar_p)]


_iphlpapi = ctypes.windll.LoadLibrary("Iphlpapi")


def _get_getadapters_result() -> ctypes.POINTER:
    buffer_size = wintypes.ULONG(15 * 1024)
    _logger.debug("Request all host ip addresses ...")
    while True:
        buffer = ctypes.create_string_buffer(buffer_size.value)
        return_code = _iphlpapi.GetAdaptersAddresses(
            wintypes.ULONG(socket.AF_INET),
            wintypes.ULONG(0),
            None,
            ctypes.byref(buffer),
            ctypes.byref(buffer_size))
        if return_code != ERROR_BUFFER_OVERFLOW:
            break
    if return_code != NO_ERROR:
        raise ctypes.WinError()
    return ctypes.cast(buffer, ctypes.POINTER(_Adapter))


def get_local_ipv4_interfaces() -> Mapping[str, Sequence[IPv4Interface]]:
    adapter_pointer = _get_getadapters_result()
    result = {}
    while adapter_pointer:
        adapter = adapter_pointer.contents
        adapter_pointer = adapter.Next
        result[adapter.FriendlyName] = adapter.interfaces_list()
    return result
