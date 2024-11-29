# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import ast
import tokenize
from typing import Sequence


def is_multiline(node: ast.expr):
    return node.lineno < node.end_lineno


def extended(lines, item):
    return extended_up(item, lines), extended_down(item, lines)


def extended_up(node: ast.AST, lines: Sequence[str]):
    """If parentized, return the line of open parentesis.

    >>> from linter._display import _Code
    >>> code = _Code('''
    ...     q = (
    ...         # Comment
    ...         'abc'
    ...         'abc')
    ...     ''')
    >>> extended_up(code.tree().body[0].value, code.lines())
    1
    """
    if node.col_offset == _line_start(lines[node.lineno - 1]):
        i1 = node.lineno  # Lines are 1-based
        while True:
            i1 -= 1  # Go line above
            if i1 < 1:
                break
            elif _line_start(lines[i1 - 1]) != len(lines[i1 - 1]):
                if _ends_with(lines[i1 - 1], '('):
                    return i1
                else:
                    break
            else:
                pass
    return node.lineno


def extended_down(node: ast.AST, lines: Sequence[str]):
    if node.end_lineno - 1 + 1 < len(lines):
        if node.end_col_offset == _line_end(lines[node.end_lineno - 1]):
            if _starts_with(lines[node.end_lineno - 1 + 1], ')'):
                return node.end_lineno + 1
    return node.end_lineno


def _starts_with(line: str, prefix: str):
    return line.lstrip().startswith(prefix)


def _ends_with(line: str, suffix: str):
    return line.endswith(suffix, None, _line_end(line))


def _line_start(line: str):
    for i, c in enumerate(line):
        if not c.isspace():
            if c == '#':
                break
            return i
    return len(line)


def _line_end(line: str):
    """Remove trailing whitespace and comment.

    >>> _line_end('    yield 123  # Comment')
    13
    """
    result = 0
    readline = iter([line.encode()]).__next__
    gen = tokenize.tokenize(readline)
    tokens = []
    while True:
        try:
            tokens.append(next(gen))
        except tokenize.TokenError:
            break
        except StopIteration:
            break
    for token in tokens:
        if token.exact_type == tokenize.COMMENT:
            return result
        elif token.exact_type == tokenize.NL:
            pass
        else:
            [_, result] = token.end
    return result
