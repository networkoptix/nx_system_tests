# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from __future__ import annotations

import json
from abc import abstractmethod
from uuid import UUID

from mediaserver_api._base_resource import BaseResource


class _BaseServer(BaseResource):

    def __init__(self, raw_data):
        super().__init__(raw_data, resource_id=UUID(raw_data['id']))
        self.name = raw_data['name']
        # https://networkoptix.atlassian.net/browse/VMS-42329
        self.status = raw_data.get('status', 'Offline')
        self._backup_bitrate = raw_data.get('backupBitrate')
        self._backup_bitrate_bps = raw_data.get('backupBitrateBytesPerSecond', [])
        self._backup_days_of_week = raw_data.get('backupDaysOfTheWeek')
        self._backup_duration = raw_data.get('backupDuration')
        self._backup_start = raw_data.get('backupStart')
        self._backup_type = raw_data.get('backupType')
        flags = raw_data['flags']
        self._flags = set(flags.split('|')) if flags else set()
        self._max_cameras = raw_data.get('maxCameras')
        self.locations = self._get_locations(raw_data)
        self._os_info = self._get_os_info(raw_data)
        self._parameters = self._params(raw_data)
        self.url = raw_data['url']
        self._version = raw_data['version']

    def __repr__(self):
        return f'<_Server {self.name} {self.id}>'

    @classmethod
    def _list_compared_attributes(cls):
        return [
            '_backup_bitrate',
            '_backup_bitrate_bps',
            '_backup_days_of_week',
            '_backup_duration',
            '_backup_start',
            '_backup_type',
            '_flags',
            'locations',
            '_max_cameras',
            'name',
            '_os_info',
            '_parameters',
            'status',
            'url',
            '_version',
            ]

    @staticmethod
    @abstractmethod
    def _get_locations(raw_data):
        pass

    @staticmethod
    @abstractmethod
    def _get_os_info(raw_data):
        pass

    @staticmethod
    @abstractmethod
    def _params(raw_data):
        pass


class ServerV0(_BaseServer):

    def __init__(self, raw_data):
        super().__init__(raw_data)
        self._allow_auto_redundancy = raw_data['allowAutoRedundancy']
        self._parent_id = UUID(raw_data['parentId'])
        self._system_info = raw_data['systemInfo']
        self._type_id = UUID(raw_data['typeId'])

    @classmethod
    def _list_compared_attributes(cls):
        base_attributes = super()._list_compared_attributes()
        version_specific_attributes = [
            '_allow_auto_redundancy',
            '_parent_id',
            '_system_info',
            '_type_id',
            ]
        return base_attributes + version_specific_attributes

    @staticmethod
    def _get_locations(raw_data):
        ip_addresses = raw_data['networkAddresses']
        return set(ip_addresses.split(';')) if ip_addresses else set()

    @staticmethod
    def _get_os_info(raw_data):
        raw_info = raw_data['osInfo'] or '{}'
        return json.loads(raw_info)

    @staticmethod
    def _params(raw_data):
        parameters = {p['name']: p['value']for p in raw_data['addParams']}
        return parameters


class ServerV1(_BaseServer):

    def __init__(self, raw_data):
        super().__init__(raw_data)
        self._is_failover_enabled = raw_data.get('isFailoverEnabled')

    @classmethod
    def _list_compared_attributes(cls):
        base_attributes = super()._list_compared_attributes()
        version_specific_attributes = ['_is_failover_enabled']
        return base_attributes + version_specific_attributes

    @staticmethod
    def _get_locations(raw_data):
        return raw_data.get('endpoints')

    @staticmethod
    def _get_os_info(raw_data):
        return raw_data['osInfo']

    @staticmethod
    def _params(raw_data):
        return raw_data['parameters']
