# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from __future__ import annotations

from collections.abc import Collection
from copy import deepcopy
from uuid import UUID

from mediaserver_api._base_resource import BaseResource


class Layout(BaseResource):

    def __init__(self, raw_data):
        super().__init__(raw_data, resource_id=UUID(raw_data['id']))
        self._background_height = raw_data['backgroundHeight']
        self._background_image_filename = raw_data['backgroundImageFilename']
        self._background_opacity = raw_data['backgroundOpacity']
        self._background_width = raw_data['backgroundWidth']
        self._cell_aspect_ratio = raw_data['cellAspectRatio']
        self._cell_spacing = raw_data['cellSpacing']
        self._fixed_height = raw_data['fixedHeight']
        self._fixed_width = raw_data['fixedWidth']
        self._is_locked = raw_data['locked']
        self._items = raw_data['items']
        self._logical_id = raw_data['logicalId']
        self.name = raw_data['name']
        self._parent_id = UUID(raw_data['parentId'])
        self._type_id = raw_data.get('typeId')
        self._url = raw_data.get('url')
        self.items = deepcopy(raw_data['items'])
        for item in self.items:
            item['id'] = UUID(item['id'])
            item['resourceId'] = UUID(item['resourceId'])

    @classmethod
    def _list_compared_attributes(cls):
        return [
            '_background_height',
            '_background_image_filename',
            '_background_opacity',
            '_background_width',
            '_cell_aspect_ratio',
            '_cell_spacing',
            '_fixed_height',
            '_fixed_width',
            '_is_locked',
            '_items',
            '_logical_id',
            'name',
            '_parent_id',
            '_type_id',
            '_url',
            ]

    def resources(self) -> Collection[UUID]:
        return {item['resourceId'] for item in self.items}
