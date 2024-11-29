# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import socket
import struct
from contextlib import contextmanager

from doubles.dnssd._common_types import Formatter
from doubles.dnssd._common_types import Section


class ProtocolMessage(Formatter):

    def __init__(self):
        transaction_id = 0x0000
        is_a_response = True
        is_authoritative = True
        self._packet = bytearray()
        self.append_short(transaction_id)
        self.append_short(is_a_response << 15 | is_authoritative << 10)
        self.append_short(0)  # Questions
        self._answer_count_offset = len(self._packet)
        self.append_short(0)  # Answer
        self.append_short(0)  # Authority
        self.append_short(0)  # Additional
        self._domain_name_cache = {}  # Name -> offset.

    def data(self) -> bytes:
        return self._packet

    def start_section(self, section: Section):
        if section != Section.ANSWER:
            raise NotImplementedError("Only Answer is supported for now")

    def increment_record_counter(self):
        [i] = struct.unpack_from('!H', self._packet, self._answer_count_offset)
        i += 1
        struct.pack_into('!H', self._packet, self._answer_count_offset, i)

    def append_domain_name(self, domain_name: str):
        if not domain_name:
            self._packet.append(0)
        elif domain_name in self._domain_name_cache:
            cached_offset = self._domain_name_cache[domain_name]
            self.append_short(0xC000 | cached_offset)
        else:
            offset = len(self._packet)
            head, tail = domain_name.split('.', 1)
            self.append_character_string(head)
            self.append_domain_name(tail)
            self._domain_name_cache[domain_name] = offset

    def append_character_string(self, data: str) -> None:
        encoded = data.encode('ascii')
        self._packet.append(len(encoded))
        self._packet.extend(encoded)

    def append_ipv4(self, address):
        data = socket.inet_aton(address)
        self._packet.extend(data)

    def append_long(self, value: int):
        self._packet.extend(struct.pack('!L', value))

    def append_short(self, value):
        self._packet.extend(struct.pack('!H', value))

    @contextmanager
    def counting_size(self):
        size_offset = len(self._packet)
        self.append_short(0)
        data_offset = len(self._packet)
        yield
        size = len(self._packet) - data_offset
        struct.pack_into('!H', self._packet, size_offset, size)
