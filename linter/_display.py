# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import ast
import io
import tokenize
from textwrap import dedent
from typing import Sequence


def print_violations(violations):
    count = 0
    for violation in violations:
        count += 1
        print("===== Violation =====")
        violation.print()
    if count == 0:
        print("===== OK =====")
    else:
        print("===== Not OK =====")


class _Code:

    def __init__(self, code: str):
        code = dedent(code.lstrip('\n'))
        self._lines = code.splitlines(keepends=True)
        self._tokens = [*tokenize.tokenize(io.BytesIO(code.encode()).readline)]
        self._tree = ast.parse(code)

    def tree(self) -> 'ast.Module':
        return self._tree

    def lines(self) -> Sequence[str]:
        return self._lines

    def tokens(self) -> 'Sequence[tokenize.Token]':
        return self._tokens


class _Violation:

    def __init__(self, pos: '_Pos', message):
        self._pos = pos
        self._message: str = message

    def print(self):
        self._pos.print(self._message)


class ASTViolation(_Violation):

    def __iter__(self):
        return iter((*self._pos.as_flake8(), self._message, None))


class _Pos:

    def __init__(self, lines: Sequence[str], lineno: int, col_offset: int):
        self._lines = lines
        self._lineno = lineno  # 1-based
        self._col_offset = col_offset  # 0-based

    def as_flake8(self):
        return self._lineno, self._col_offset + 1

    def print(self, message: str):
        for i, line in enumerate(self._lines):
            print(line.rstrip())
            if i == self._lineno - 1:
                [number, *_] = message.split()
                print(' ' * self._col_offset + '^', number)


class Start(_Pos):

    def __init__(self, lines, node: ast.AST):
        super().__init__(lines, node.lineno, node.col_offset)
