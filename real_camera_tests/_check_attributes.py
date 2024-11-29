# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
from abc import ABCMeta
from abc import abstractmethod
from typing import Any
from typing import Collection
from typing import Mapping
from typing import Union


class _Expectation(metaclass=ABCMeta):

    @abstractmethod
    def compare(self, actual):
        pass


class EqualTo(_Expectation):

    def __init__(self, expected: Any):
        self._expected = expected

    def compare(self, actual: Union[str, int]):
        return self._expected == actual

    def __repr__(self):
        return f"{self.__class__.__name__}({self._expected!r})"


class Vendor(_Expectation):

    def __init__(self, expected: Collection[str]):
        self._expected = expected

    def compare(self, actual: str):
        return any(actual.lower() == value.lower() for value in self._expected)

    def __repr__(self):
        return f"{self.__class__.__name__}({self._expected!r})"


class ExpectedAttributes:

    def __init__(self, expected: Mapping[str, _Expectation]):
        self._expected = expected

    def validate(self, actual: Mapping[str, Union[str, int]]):
        errors = []
        for key, checker in self._expected.items():
            actual_value = actual.get(key)
            if not checker.compare(actual_value):
                errors.append({key: f"Expected: {checker!r}, Actual: {actual_value}"})
        return errors

    def _as_str_map(self):
        return {key: f"{checker!r}" for key, checker in self._expected.items()}

    def __repr__(self):
        return f"{self.__class__.__name__}({json.dumps(self._as_str_map(), indent=4)})"

    def model(self):
        return self._expected.get('model')

    def firmware(self):
        return self._expected.get('firmware')

    def vendor(self):
        return self._expected.get('vendor')
