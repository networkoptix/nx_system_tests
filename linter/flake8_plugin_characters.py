# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import fnmatch
import unicodedata


def prohibited_unicode_characters(physical_line: str):
    prohibited = [
        '* QUOTATION MARK',
        ]
    for i, c in enumerate(physical_line):
        if not c.isascii():
            name = unicodedata.name(c)
            for pattern in prohibited:
                if fnmatch.fnmatch(name, pattern):
                    yield i, "X004 Prohibited non-ASCII character: " + name
