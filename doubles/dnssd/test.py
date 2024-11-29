# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import io
from contextlib import contextmanager

from doubles.dnssd._common_types import Answer
from doubles.dnssd._common_types import Formatter
from doubles.dnssd._common_types import Section
from doubles.dnssd._services import DNSSDWebService


class VisualDump(Formatter):

    def __init__(self):
        self._io = io.StringIO()
        self._record_count = 0
        self._indent = 0
        self._write_line("Header".center(80, '='))

    def data(self) -> str:
        return self._io.getvalue()

    def start_section(self, section_name: Section):
        self._write_line(section_name.value.center(80, '='))

    def increment_record_counter(self):
        self._write_line(f"Record {self._record_count}".center(80, '-'))
        self._record_count += 1

    def append_domain_name(self, domain_name: str):
        self._write_line(f"Domain name: {domain_name}")

    def append_character_string(self, data: str) -> None:
        self._write_line(f"Character name: {data}")

    def append_ipv4(self, address):
        self._write_line(f"IPv4: {address}")

    def append_long(self, value: int):
        self._write_line(f"Long: {value:d} 0x{value:08x}")

    def append_short(self, value):
        self._write_line(f"Short: {value:d} 0x{value:04x}")

    @contextmanager
    def counting_size(self):
        self._write_line("Data:")
        self._indent += 1
        yield
        self._indent -= 1

    def _write_line(self, string):
        self._io.write('    ' * self._indent)
        self._io.write(string)
        self._io.write('\n')


if __name__ == '__main__':
    f = VisualDump()
    Answer([DNSSDWebService('mpjpeg2', '10.0.0.34', 12312, '/1.mjpeg')]).append_to(f)
    print(f.data())
