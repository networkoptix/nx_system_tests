# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import io
from html.parser import HTMLParser
from typing import Sequence
from urllib.parse import urljoin


def parse_links(url, stream) -> Sequence[str]:
    parser = _LinkParser(url)
    decoded = io.TextIOWrapper(stream, 'utf8', 'backslashreplace')
    while chunk := decoded.read():
        parser.feed(chunk)
    links = parser.links
    parser.close()
    return links


class _LinkParser(HTMLParser):

    def __init__(self, base):
        super().__init__()
        self._base_seen = False
        self._base = base
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == 'base':
            if self._base_seen:
                return
            self._base_seen = True
            for key, value in attrs:
                if key == 'href':
                    self._base = urljoin(self._base, value)  # May be relative.
            return
        if tag == 'a':
            for key, value in attrs:
                if key == 'href':
                    url = urljoin(self._base, value)  # Treat href as usual.
                    self.links.append(url)
            return
