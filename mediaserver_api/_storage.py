# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from __future__ import annotations
from __future__ import annotations

from uuid import UUID

from mediaserver_api._base_resource import BaseResource


class Storage(BaseResource):
    """Make _Storage object from api/storageSpace data.

    _Storage is constructed from 'api/storageSpaces', not from 'ec2/getStorages', so inheritance
    from _BaseObject is not needed.
    """

    def __init__(self, raw_data):
        super().__init__(raw_data, resource_id=UUID(raw_data['storageId']))
        self.path = raw_data['url']
        self.space = int(raw_data['totalSpace'])
        self.is_backup = raw_data['isBackup']
        self.is_enabled = raw_data['isUsedForWriting']
        self.is_writable = raw_data['isWritable']
        self.type = raw_data['storageType']
        self.free_space = int(raw_data['freeSpace'])
        self.reserved_space = int(raw_data['reservedSpace'])
        self.is_online = int(raw_data['isOnline'])
        self._status_raw = raw_data.get('storageStatus')
        if self._status_raw == '':
            raise RuntimeError("Value of storageStatus must not be empty.")
        elif self._status_raw == 'none':
            self.status = []
        elif self._status_raw is None:
            self.status = raw_data['runtimeFlags'] + raw_data['persistentFlags']
        else:
            self.status = raw_data['storageStatus'].split('|')
        self._is_external = raw_data['isExternal']

    def __repr__(self):
        free_gb = self.free_space / 1024 ** 3
        reserved_gb = self.reserved_space / 1024 ** 3
        total_gb = self.space / 1024 ** 3
        space_summary = f"{free_gb:.1f}G/{reserved_gb:.1f}G/{total_gb:.1f}G"
        return f'<{self.__class__.__name__} {self.path} {space_summary} {self._status_raw}>'

    @classmethod
    def _list_compared_attributes(cls):
        return [
            'is_backup',
            'is_enabled',
            '_is_external',
            'is_online',
            'is_writable',
            'path',
            'reserved_space',
            'space',
            'status',
            'type',
            ]


class _StorageType:
    MAIN = 1
    BACKUP = 0


class WrongPathError(Exception):
    pass


class StorageUnavailable(Exception):
    pass
