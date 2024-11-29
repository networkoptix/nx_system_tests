# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from typing import Iterable

from os_access._winrm import WmiInvokeFailed

_logger = logging.getLogger(__name__)


class KeyNotFoundError(Exception):
    pass


class ValueNotFoundError(Exception):
    pass


_types = {
    1: 'REG_SZ', 2: 'REG_EXPAND_SZ', 7: 'REG_MULTI_SZ',
    4: 'REG_DWORD', 11: 'REG_QWORD',
    3: 'REG_BINARY',
    }


_hives = {
    'HKEY_CLASSES_ROOT': 2147483648, 'HKCR': 2147483648,
    'HKEY_CURRENT_USER': 2147483649, 'HKCU': 2147483649,
    'HKEY_LOCAL_MACHINE': 2147483650, 'HKLM': 2147483650,
    'HKEY_USERS': 2147483651, 'HKU': 2147483651,
    'HKEY_CURRENT_CONFIG': 2147483653, 'HKCC': 2147483653,
    }


def _key_args(key):
    hive_str, key_name = key.split('\\', 1)
    hive_int = _hives[hive_str]
    return {'hDefKey': hive_int, 'sSubKeyName': key_name}


class WindowsRegistry:

    def __init__(self, winrm):
        self._winrm = winrm
        self._ns = 'http://schemas.microsoft.com/wbem/wsman/1/wmi/root/cimv2/StdRegProv'

    def _invoke(self, method, args):
        return self._winrm.wsman_invoke(self._ns, {}, method, args)

    def create_key(self, key: str):
        """Create, if don't exist, key and its parents."""
        self._invoke('CreateKey', _key_args(key))

    def delete_key(self, key: str):
        try:
            self._invoke('DeleteKey', _key_args(key))
        except WmiInvokeFailed as e:
            if e.return_value == 2:
                _logger.warning("There is no such key: %s", key)
            else:
                raise

    def list_values(self, key: str):
        try:
            response = self._invoke('EnumValues', _key_args(key))
        except WmiInvokeFailed as e:
            if e.return_value == 2:
                raise KeyNotFoundError(key)
            else:
                raise
        result = []
        types_raw = response.get(self._ns + ':Types', [])
        names = response.get(self._ns + ':sNames', [])
        if type(names) is not list:
            # xmltodict does not produce dict for single element by default
            types_raw = [types_raw]
            names = [names]
        for type_raw, name in zip(types_raw, names):
            type_str = _types[int(type_raw)]
            result.append((name, type_str))
        return result

    def list_keys(self, key: str):
        response = self._invoke('EnumKey', _key_args(key))
        names = response.get(self._ns + ':sNames', [])
        if type(names) is list:
            return names
        else:
            # xmltodict does not produce dict for single element by default
            return [names]

    def key_exists(self, key):
        try:
            self.list_values(key)  # Check for existence.
        except KeyNotFoundError:
            return False
        return True

    def _get(self, method, key, name, response_field):
        _logger.debug("Get value: %s!%s", key, name)
        args = {**_key_args(key), 'sValueName': name}
        try:
            response = self._invoke(method, args)
        except WmiInvokeFailed as e:
            if e.return_value == 1:
                raise ValueNotFoundError("{}!{}".format(key, name))
            elif e.return_value == 0x80041005:
                # See: https://docs.microsoft.com/en-us/windows/win32/wmisdk/wmi-error-constants
                raise TypeError(f"{key}!{name}")
            else:
                raise
        return response.get(self._ns + ':' + response_field, [])

    def get_string(self, key: str, name: str):
        return self._get('GetStringValue', key, name, 'sValue')

    def get_expanded_string(self, key: str, name: str):
        return self._get('GetExpandedStringValue', key, name, 'sValue')

    def get_multi_string(self, key: str, name: str):
        data = self._get('GetMultiStringValue', key, name, 'sValue')
        if not isinstance(data, list):
            return [data]
        return data

    def get_dword(self, key: str, name: str):
        return int(self._get('GetDWORDValue', key, name, 'uValue'))

    def get_qword(self, key: str, name: str):
        return int(self._get('GetQWORDValue', key, name, 'uValue'))

    def get_binary(self, key: str, name: str):
        result = self._get('GetBinaryValue', key, name, 'uValue')
        return bytes(map(int, result))

    def _set(self, method, key, name, data_arg_name, data):
        _logger.debug("Set value: %s!%s = %s", key, name, data)
        args = {**_key_args(key), 'sValueName': name, data_arg_name: data}
        self._invoke(method, args)

    def set_string(self, key: str, name: str, data: str):
        self._set('SetStringValue', key, name, 'sValue', data)

    def set_expanded_string(self, key: str, name: str, data: str):
        self._set('SetExpandedStringValue', key, name, 'sValue', data)

    def set_multi_string(self, key: str, name: str, data: Iterable[str]):
        self._set('SetMultiStringValue', key, name, 'sValue', [*data])

    def set_dword(self, key: str, name: str, data: int):
        if not 0 <= data <= 2 ** 32 - 1:
            raise ValueError("Doesn't fit DWORD: {0}".format(data))
        self._set('SetDWORDValue', key, name, 'uValue', data)

    def set_qword(self, key: str, name: str, data: int):
        if not 0 <= data <= 2 ** 64 - 1:
            raise ValueError("Doesn't fit QWORD: {0}".format(data))
        self._set('SetQWORDValue', key, name, 'uValue', data)

    def set_binary(self, key: str, name: str, data: bytes):
        self._set('SetBinaryValue', key, name, 'uValue', data)

    def delete_value(self, key: str, name: str):
        try:
            self._invoke('DeleteValue', {**_key_args(key), 'sValueName': name})
        except WmiInvokeFailed as err:
            if err.return_value == 2:  # Value does not exist
                return
            raise
