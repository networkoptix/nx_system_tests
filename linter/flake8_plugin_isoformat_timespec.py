# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
r"""Require timespec in datetime.isoformat() to avoid inconsistent auto format.

From datetime.isoformat() docsrting:

    The full format looks like 'YYYY-MM-DD HH:MM:SS.mmmmmm'.
    By default, the fractional part is omitted if self.microsecond == 0.

How it should be:

>>> _check('''pts.isoformat(timespec='milliseconds')''')
===== OK =====

Positional argument is also recognized:

>>> _check('''pts.isoformat(' ', 'milliseconds')''')
===== OK =====

Typical problem:

>>> _check('''started_at.isoformat()''')
===== Violation =====
started_at.isoformat()
          ^ X027
===== Not OK =====

>>> _check('''pts.isoformat(' ')''')
===== Violation =====
pts.isoformat(' ')
   ^ X027
===== Not OK =====

Not applicable to date.isoformat():

>>> _check('''report.current_date.isoformat()''')
===== OK =====

Whether this is a datetime or a date is determined by variable name,
attribute name, dict key or method name:

>>> _check('''create_time().isoformat()''')
===== Violation =====
create_time().isoformat()
             ^ X027
===== Not OK =====

>>> _check('''period[0][-1].isoformat()''')
===== Violation =====
period[0][-1].isoformat()
             ^ X027
===== Not OK =====

>>> _check('''data['value'].isoformat()''')
===== Violation =====
data['value'].isoformat()
             ^ X027
===== Not OK =====

>>> _check('''old_days[-1].isoformat()''')
===== OK =====

Not applied to unrelated calls:

>>> _check('''datetime.now()''')
===== OK =====
"""
from ast import Attribute
from ast import Call
from ast import Constant
from ast import Module
from ast import Name
from ast import Subscript
from ast import walk
from typing import Optional
from typing import Sequence

from linter._display import ASTViolation
from linter._display import _Code
from linter._display import _Pos
from linter._display import print_violations


def timespec_in_datetime_isoformat(tree: Module, lines: Sequence[str]):
    for node in walk(tree):
        if isinstance(node, Call) and isinstance(node.func, Attribute):
            if node.func.attr == 'isoformat':
                name = _extract_name(node.func.value)
                if name is not None and not _looks_like_date(name):
                    has_arg = len(node.args) >= 2
                    has_kwarg = any(k.arg == 'timespec' for k in node.keywords)
                    if not has_arg and not has_kwarg:
                        lineno = node.func.value.end_lineno
                        col_offset = node.func.value.end_col_offset
                        yield ASTViolation(
                            _Pos(lines, lineno, col_offset),
                            "X027 no timespec kwarg in datetime.isoformat()",
                            )


def _extract_name(node) -> Optional[str]:
    if isinstance(node, Attribute):
        return node.attr
    elif isinstance(node, Name):
        return node.id
    elif isinstance(node, Subscript):
        if isinstance(node.slice, Constant) and isinstance(node.slice.value, str):
            return node.slice.value
        else:
            return _extract_name(node.value)
    elif isinstance(node, Call):
        return _extract_name(node.func)
    else:
        return None


def _looks_like_date(name) -> bool:
    allowed = ['date', 'dates', 'day', 'days', 'today']
    return any(word in name.split('_') for word in allowed)


def _check(code):
    """Shortcut for code in docstring."""
    code = _Code(code)
    print_violations(timespec_in_datetime_isoformat(tree=code.tree(), lines=code.lines()))
