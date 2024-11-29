# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from typing import Collection
from typing import Mapping
from uuid import UUID


class AnalyticsEngineCollection:

    def __init__(self, raw):
        self._raw = raw

    def __repr__(self):
        return f'<{self.__class__.__name__} with {len(self._raw)} items>'

    def get_by_exact_name(self, name) -> 'AnalyticsEngine':
        for raw in self._raw:
            if raw['name'] == name:
                return AnalyticsEngine(raw)
        raise AnalyticsEngineNotFound(f"{self!r} does not contain {name!r}")

    def get_stub(self, *names) -> 'AnalyticsEngine':
        for raw in self._raw:
            # VMS-42597: Stub Analytics Plugin: Change sub-plugin names
            for name in names:
                if raw['name'] in ('Stub: ' + name, 'Stub, ' + name):
                    return AnalyticsEngine(raw)
        raise AnalyticsEngineNotFound(f"{self!r} does not contain stub {names!r}")

    def list_engines(self) -> Collection['AnalyticsEngine']:
        return [AnalyticsEngine(raw) for raw in self._raw]

    def get_by_id(self, engine_id: UUID) -> 'AnalyticsEngine':
        for raw in self._raw:
            if UUID(raw['id']) == engine_id:
                return AnalyticsEngine(raw)
        raise AnalyticsEngineNotFound(f"{self!r} does not contain engine with id {engine_id}")


class AnalyticsEngine:

    def __init__(self, raw: Mapping):
        self._raw = raw

    def id(self) -> UUID:
        return UUID(self._raw['id'])

    def name(self) -> str:
        return self._raw['name']


class AnalyticsEngineNotFound(Exception):
    pass


class AnalyticsEngineSettings:

    def __init__(self, data):
        self.model = data['settingsModel']
        self.values = data['settingsValues']
        self.message_to_user = data.get('messageToUser')
