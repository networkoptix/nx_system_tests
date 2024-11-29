# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
def backslashes_for_line_continuation(physical_line: str):
    if physical_line.endswith('\\\n'):
        i = len(physical_line) - 2
        yield i, "X006 Backslashes for line continuation are prohibited"
