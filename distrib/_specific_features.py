# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from __future__ import annotations

import logging
import re

_logger = logging.getLogger(__name__)


class SpecificFeatures:

    def __init__(self, raw: bytes):
        matches = re.findall(rb'^\s*(\w+)\s*=\s*(\d+)\s*$', raw, re.MULTILINE)
        self._dict = {m[0].decode(): int(m[1]) for m in matches}
        _logger.debug("%r: Parsed %r", self, self._dict)

    def __repr__(self):
        return '<SpecificFeatures>'

    def get(self, name: str, default: int = 0) -> int:
        return self._dict.get(name, default)
