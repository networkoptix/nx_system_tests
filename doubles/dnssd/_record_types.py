# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from typing import Sequence

from doubles.dnssd._common_types import CharacterString
from doubles.dnssd._common_types import Composite
from doubles.dnssd._common_types import DomainName
from doubles.dnssd._common_types import InternetAddress
from doubles.dnssd._common_types import RecordData
from doubles.dnssd._common_types import Short


class ARecordData(RecordData):

    def __init__(self, address: str):
        super().__init__(1, InternetAddress(address))


class TxtRecordData(RecordData):

    def __init__(self, texts: Sequence[str]):
        super().__init__(16, Composite([
            CharacterString(text)
            for text in texts
            ]))


class SrvRecordData(RecordData):

    def __init__(
            self,
            target: str,
            port: int,
            priority: int = 0,
            weight: int = 0,
            ):
        super().__init__(33, Composite([
            Short(priority),
            Short(weight),
            Short(port),
            DomainName(target),
            ]))


class PtrRecordData(RecordData):

    def __init__(self, domain_name):
        super().__init__(12, DomainName(domain_name))
