# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import socket
import time
from contextlib import closing
from typing import Collection
from typing import Sequence
from typing import Tuple

from doubles.dnssd._common_types import Answer
from doubles.dnssd._common_types import ServiceAdvertisement
from doubles.dnssd._protocol_formatter import ProtocolMessage


class DNSSDScope:

    def __init__(self, locations: Collection[Tuple[str, int]]):
        self._locations: Collection[Tuple[str, int]] = locations

    def advertise_in_foreground(self, services: Sequence[ServiceAdvertisement]):
        packet = ProtocolMessage()
        Answer(services).append_to(packet)
        with closing(socket.socket(socket.AF_INET, socket.SOCK_DGRAM)) as s:
            while True:
                for location in self._locations:
                    s.sendto(packet.data(), location)
                time.sleep(1)

    def advertise_once(self, services: Sequence[ServiceAdvertisement]):
        packet = ProtocolMessage()
        Answer(services).append_to(packet)
        with closing(socket.socket(socket.AF_INET, socket.SOCK_DGRAM)) as s:
            for location in self._locations:
                s.sendto(packet.data(), location)
