# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from __future__ import annotations

from uuid import UUID

from mediaserver_api._base_resource import BaseResource


class WebPage(BaseResource):

    def __init__(self, raw_data):
        super().__init__(raw_data, resource_id=UUID(raw_data['id']))

    def name(self) -> str:
        return self.raw_data['name']
