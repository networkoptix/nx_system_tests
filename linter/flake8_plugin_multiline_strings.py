# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import re
import tokenize
from typing import Sequence


def multiline_string_always_in_parens(logical_line, tokens: Sequence[tokenize.TokenInfo]):
    s = ''.join(
        'v' if t.type == tokenize.NAME else
        's' if t.type == tokenize.STRING else
        'n' if t.type == tokenize.NL else
        '=' if t.string == '=' else
        '_'
        for t in tokens)
    for m in re.finditer(r'v=(s+n|n+s)', s):
        yield m.start(), "X005 Multiline string after kwarg name must be enclosed with parentheses"
