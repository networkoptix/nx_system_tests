# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import functools
import struct

from os_access._winrm import WinRM
from os_access._winrm import WmiFault


class _SecurityIdentifier:

    def __init__(self, as_str):
        self.as_str = as_str
        [letter_s, *numbers] = as_str.split('-')
        if letter_s != 'S':
            raise ValueError("SID must have S-... form: {}".format(as_str))
        # See: https://docs.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-sid
        [revision, authority, *sub_authorities] = [int(n) for n in numbers]
        self.as_bytes = struct.pack(
            '<bb6b{}I'.format(len(sub_authorities)),
            revision,
            len(sub_authorities),
            *struct.pack('>Q', authority)[2:],
            *sub_authorities)
        self.for_xmldict = [*self.as_bytes]


class UserAccount:

    def __init__(self, winrm: WinRM, local_name_with_domain: str):
        self._winrm = winrm
        self.name_with_domain = local_name_with_domain
        [domain, self.name] = local_name_with_domain.split('\\')
        data = self._winrm.wsman_get(
            'Win32_UserAccount', {
                'Domain': domain,
                'Name': self.name,
                })
        self.sid = _SecurityIdentifier(data['SID'])

    @functools.lru_cache()
    def profile(self):
        return UserProfile(self._winrm, self.sid.as_str)


class UserProfile:

    def __init__(self, winrm: WinRM, sid: str):
        self._winrm = winrm
        self._sid = sid
        try:
            data = self._winrm.wsman_get(
                'Win32_UserProfile', {
                    'SID': self._sid,
                    })
        except WmiFault as e:
            if '0x80070002' in str(e):
                raise RuntimeError(f"Account {sid} doesn't have a profile dir")
            raise
        self.local_path = data['LocalPath']
