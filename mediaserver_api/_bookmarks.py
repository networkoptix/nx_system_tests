# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from __future__ import annotations

from abc import abstractmethod
from uuid import UUID

from mediaserver_api._base_resource import BaseResource


class _BaseBookmark(BaseResource):

    def __init__(self, raw_data):
        resource_id = self._resource_id(raw_data)
        super().__init__(raw_data, resource_id=resource_id)
        self.name = raw_data['name']
        self.camera_id = UUID(self._camera_id(raw_data))
        self.start_time_ms = int(raw_data.get('startTimeMs', 0))
        self.duration_ms = int(raw_data.get('durationMs', 0))
        self.description = raw_data.get('description', '')

    @abstractmethod
    def _resource_id(self, raw_data: dict):
        pass

    @abstractmethod
    def _camera_id(self, raw_data: dict):
        pass

    def __repr__(self):
        return (
            f'<{self.__class__.__name__}: Name={self.name}, StartTimeMs={self.start_time_ms}, '
            f'DurationMs={self.duration_ms}, Description={self.description}>'
            )


class _BookmarkV0(_BaseBookmark):

    def _resource_id(self, raw_data: dict):
        return UUID(raw_data['guid'])

    def _camera_id(self, raw_data: dict):
        return raw_data['cameraId']


class _BookmarkV1(_BaseBookmark):

    def _resource_id(self, raw_data: dict):
        return UUID(raw_data['id'])

    def _camera_id(self, raw_data: dict):
        return raw_data['deviceId']


class _BookmarkV3(_BaseBookmark):

    def _resource_id(self, raw_data: dict):
        return raw_data['id']

    def _camera_id(self, raw_data: dict):
        return raw_data['deviceId']
