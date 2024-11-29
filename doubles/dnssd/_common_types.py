# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from abc import ABCMeta
from abc import abstractmethod
from enum import Enum
from typing import Sequence


class _Leaf(metaclass=ABCMeta):

    @abstractmethod
    def append_to(self, response: 'Formatter') -> None:
        pass


class Composite(_Leaf):

    def __init__(self, pieces: Sequence[_Leaf]):
        self._pieces: Sequence[_Leaf] = pieces

    def append_to(self, response: 'Formatter') -> None:
        for piece in self._pieces:
            piece.append_to(response)


class ServiceAdvertisement(Composite):
    """A composite that represents resource. Just for typing."""

    def __init__(self, resource_records: 'Sequence[Record]'):
        super().__init__(resource_records)


class Answer(_Leaf):

    def __init__(self, services: Sequence[ServiceAdvertisement]):
        self._services = services

    def append_to(self, response: 'Formatter') -> None:
        response.start_section(Section.ANSWER)
        for service in self._services:
            service.append_to(response)


class Record(_Leaf):

    def __init__(self, name: str, data: 'RecordData'):
        self._name: str = name
        self._data: RecordData = data

    def append_to(self, response: 'Formatter') -> None:
        response.increment_record_counter()
        response.append_domain_name(self._name)
        self._data.append_to(response)


class RecordData(Composite):

    def __init__(self, type_id: int, data: _Leaf):
        ttl_sec = 900
        dns_class = 1  # IN ("internet"). The others values are rarely used.
        cache_flush = True
        super().__init__([
            Short(type_id),
            Short(cache_flush << 15 | dns_class),
            Long(ttl_sec),
            _Sized(data),
            ])


class DomainName(_Leaf):

    def __init__(self, name: str):
        self._name = name

    def append_to(self, response: 'Formatter') -> None:
        response.append_domain_name(self._name)


class InternetAddress(_Leaf):

    def __init__(self, address: str):
        self._address: str = address

    def append_to(self, response: 'Formatter') -> None:
        response.append_ipv4(self._address)


class CharacterString(_Leaf):

    def __init__(self, value: str):
        self._value: str = value

    def append_to(self, response: 'Formatter') -> None:
        response.append_character_string(self._value)


class Short(_Leaf):

    def __init__(self, value: int):
        self._value: int = value

    def append_to(self, response: 'Formatter') -> None:
        response.append_short(self._value)


class Long(_Leaf):

    def __init__(self, value: int):
        self._value: int = value

    def append_to(self, response: 'Formatter') -> None:
        response.append_long(self._value)


class _Sized(_Leaf):

    def __init__(self, piece: _Leaf):
        self._piece: _Leaf = piece

    def append_to(self, response: 'Formatter') -> None:
        with response.counting_size():
            self._piece.append_to(response)


class Formatter(metaclass=ABCMeta):

    @abstractmethod
    def start_section(self, section_name: 'Section'):
        pass

    @abstractmethod
    def increment_record_counter(self):
        pass

    @abstractmethod
    def append_domain_name(self, domain_name: str):
        pass

    @abstractmethod
    def append_character_string(self, data: str):
        pass

    @abstractmethod
    def counting_size(self):
        pass

    @abstractmethod
    def append_ipv4(self, address: str):
        pass

    @abstractmethod
    def append_long(self, value: int):
        pass

    @abstractmethod
    def append_short(self, value: int):
        pass


class Section(Enum):
    QUESTION = 'Question'
    ANSWER = 'Answer'
    AUTHORITY = 'Authority'
    ADDITIONAL = 'Additional'
