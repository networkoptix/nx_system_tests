# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import re
import tokenize


def raise_from_none(logical_line, tokens):
    pairwise = zip(tokens[:-1], tokens[1:])
    for a, b in pairwise:
        if a.string == 'from' and b.string == 'None':
            yield a.start, "X003 raise ... from None is prohibited"


def raise_class(logical_line, tokens):
    s = ''.join(
        'r' if t.exact_type == tokenize.NAME and t.string == 'raise' else
        'N' if t.exact_type == tokenize.NAME and t.string[0].isupper() else
        'n' if t.exact_type == tokenize.NAME else
        'p' if t.exact_type == tokenize.DOT else
        'O' if t.exact_type == tokenize.LPAR else
        '' if t.exact_type == tokenize.NEWLINE else
        '' if t.exact_type == tokenize.INDENT else
        '_'
        for t in tokens)
    if re.fullmatch(r'r([nN]p)*N', s):
        yield 0, "X021 raise must be used with objects, not classes"
