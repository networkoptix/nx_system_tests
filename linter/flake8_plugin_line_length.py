# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import io
import re
import tokenize


def line_length(physical_line, max_line_length):
    if len(physical_line) <= max_line_length:
        return
    if re.match(r' *(# *)?(See:|>)', physical_line):
        return
    # print('-' * 80)
    # print(physical_line)
    tokens = []
    try:
        for t in tokenize.tokenize(io.BytesIO(physical_line.encode()).readline):
            tokens.append(t)
    except tokenize.TokenError:
        pass  # Expect an exception caused by early EOF.
    s = ''.join(
        '.' if t.type == tokenize.OP and t.string == '.' else
        ',' if t.type == tokenize.OP and t.string == ',' else
        ':' if t.type == tokenize.OP and t.string == ':' else
        '=' if t.type == tokenize.OP and t.string == '=' else
        '(' if t.type == tokenize.OP and t.string == '(' else
        ')' if t.type == tokenize.OP and t.string == ')' else
        'c' if t.type == tokenize.COMMENT else
        's' if t.type == tokenize.NUMBER else
        's' if t.type == tokenize.STRING else
        'f' if t.type == tokenize.NAME and t.string == 'from' else
        'i' if t.type == tokenize.NAME and t.string == 'import' else
        'x' if t.type == tokenize.NAME else
        '' if t.type == tokenize.ENDMARKER else
        '' if t.type == tokenize.INDENT else
        '' if t.type == tokenize.DEDENT else
        '' if t.type == tokenize.ENCODING else
        '' if t.type == tokenize.NL else
        '' if t.type == tokenize.NEWLINE else
        '_'
        for t in tokens)
    # print(s)
    # print(*tokens, sep='\n')
    if not re.fullmatch(r'x=s|s:s,|s,|x\(s\),?|x=x\(s\)|(fx(\.x)*)?ix(\.x)*', s):
        yield max_line_length, "X009 Line too long"
