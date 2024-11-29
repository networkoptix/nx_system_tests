# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID


class BaseResource:

    def __init__(self, raw_data: Mapping[str, Any], resource_id: UUID):
        self.raw_data = raw_data
        self.id = resource_id

    def __repr__(self):
        return f'<{self.__class__.__name__} {self.id}>'

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return NotImplemented
        if self._list_compared_attributes():
            return not self.diff(other)
        return self.raw_data == other.raw_data

    @classmethod
    def _list_compared_attributes(cls):
        return []

    @classmethod
    def _remove_underscore(cls, name):
        return name[1:] if name.startswith('_') else name

    @classmethod
    def _compare_dicts(cls, self, other):
        result = {}
        for removed_key in self.keys() - other.keys():
            clean_key = cls._remove_underscore(removed_key)
            result[clean_key] = {'action': 'removed', 'self': self[removed_key]}
        for key in self.keys() & other.keys():
            self_value = self[key]
            other_value = other[key]
            if self_value != other_value:
                clean_key = cls._remove_underscore(key)
                result[clean_key] = {'action': 'changed', 'self': self_value, 'other': other_value}
        for new_key in other.keys() - self.keys():
            clean_key = cls._remove_underscore(new_key)
            result[clean_key] = {'action': 'added', 'other': other[new_key]}
        return result

    def diff(self, other):
        if not isinstance(other, self.__class__):
            return NotImplemented
        result = {}
        for attr in self._list_compared_attributes():
            clean_name = self._remove_underscore(attr)
            left = getattr(self, attr)
            right = getattr(other, attr)
            if isinstance(left, dict):
                dicts_diff = self._compare_dicts(left, right)
                for key, value in dicts_diff.items():
                    result[f'{clean_name}/{key}'] = value
            elif type(left) != type(right) or left != right:
                result[clean_name] = {'action': 'changed', 'self': left, 'other': right}
        return result
