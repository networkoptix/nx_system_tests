# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
r"""Check formatting of multiline expressions.

Add a newline before the first item in multiline lists, tuples, sets, dicts,
string literals, function calls and definitions.

>>> _check('''
...     qwe = [
...         "very long item number one",
...         "another item, which is even longer and does not fit",
...         ]
...     ''')
===== OK =====

>>> _check('''
...     qwe = ["very long item number one",
...            "another item, which is even longer and does not fit",
...            ]
...     ''')
===== Violation =====
qwe = ["very long item number one",
       ^ X031
       "another item, which is even longer and does not fit",
       ]
===== Not OK =====

>>> _check('''
...     def _check_words(start_line_index,
...                      end_line_index=None,
...                      ):
...         pass
...     ''')
===== Violation =====
def _check_words(start_line_index,
                 ^ X031
                 end_line_index=None,
                 ):
    pass
===== Not OK =====

>>> _check('''
...     foo(asd, ("rty"
...               "fgh"))
...     ''')
===== Violation =====
foo(asd, ("rty"
          ^ X031
          "fgh"))
===== Not OK =====

Special case: it's OK if only the last (or the only) item contains newlines.

>>> _check('''
...     self.http_get('api/virtualCamera/status', params={
...         'cameraId': _format_uuid(camera_id),
...         })
...     ''')
===== OK =====

>>> _check(r'''
...     self.run(['fdisk', str(disk)], input=(
...         b'o\n'  # Create DOS (MBR) partition table.
...         b'w\n'  # Write changes.
...         ))
...     ''')
===== OK =====

>>> _check('''
...     def qwe():
...         yield asd(x, (  # Comment
...             "zxc"
...             "rty"))
...     ''')
===== OK =====

>>> _check('''
...     def qwe():
...         yield asd(x, (
...             "zxc"
...             "rty"))
...     ''')
===== OK =====

If an item is multiline, it may not share a line with another item.
The item that follows is visually lost.

>>> _check('''
...     self._connection.executemany(
...         'INSERT INTO releases VALUES( '
...         ':url, '
...         ':appearance_date)', values)
...    ''')
===== Violation =====
self._connection.executemany(
    'INSERT INTO releases VALUES( '
    ':url, '
    ':appearance_date)', values)
                         ^ X032
===== Not OK =====

It an item is multiline, it may not share a line with another item.
The item that follows is visually lost.

>>> _check('''
...     self._connection.executemany(
...         # Comment
...         'INSERT INTO releases VALUES( '
...         '1)')
...    ''')
===== OK =====

But if two mutiline items go one after another, closing bracket of the first
may share a line with opening bracket of the other.

>>> _check('''
...     _logger.info(
...         "HTTP API %(method)s %(url)s, "
...         "took %(duration).3f sec, "
...         "status %(status)s"
...         "", {
...             'method': method,
...             'url': url,
...             'path': path,
...             'duration': time.perf_counter() - started_at,
...             'status': response.status_code,
...             })
...     ''')
===== OK =====

Multiline string literals must be enclosed with parenteses.
It helps to avoid sutble commas at the end of some lines.
It gives another level of indent, which reflects the structure of code.

>>> _check('''
...     result = self.os_access.run(
...         command=[
...             self.os_access.find_cdb(),
...             '-c',  # Execute commands:
...             'kc;'  # current thread backtrace,
...             'q',  # quit.
...             ],
...         timeout_sec=timeout_sec,
...         )
...         ''')
===== Violation =====
result = self.os_access.run(
    command=[
        self.os_access.find_cdb(),
        '-c',  # Execute commands:
        'kc;'  # current thread backtrace,
        ^ X035
        'q',  # quit.
        ],
    timeout_sec=timeout_sec,
    )
===== Not OK =====

>>> _check('''
...     result = self.os_access.run(
...         command=[
...             self.os_access.find_cdb(),
...             '-c', (  # Execute commands:
...                 'kc;'  # current thread backtrace,
...                 'q'),  # quit.
...             ],
...         timeout_sec=timeout_sec,
...         )
...         ''')
===== OK =====

Triple-quote strings as docstrings or module-level variables are allowed.

>>> _check('''
...     def qwe():
...         \'\'\'Doc.
...
...         String.
...         \'\'\'
...     ''')
===== OK =====

>>> _check('''
...     _delayed_cat = r\'\'\'
...     timeout 1
...     more
...     \'\'\'
...     ''')
===== OK =====

Consider textwrap.dedent(), textwrap.shorten() or re.sub() for triple-quotes.

>>> _check('''
...     run_powershell_script(
...         WinRMShell(mediaserver.os_access.winrm),
...         textwrap.shorten(width=10000, text=\'\'\'
...             Write-EventLog
...                 -LogName Application
...                 -Source $source
...                 -EventID $event_id
...             \'\'\'),
...         )
... ''')
===== OK =====

>>> _check('''
...     outcome = self.os_access.run([
...         str(app_dir),
...         str(file_path),
...         re.sub(r'\\n\\s*', '', \'\'\'
...             #transcode{
...                 vfilter=scene{
...                     sprefix=%(stem)s,
...                     sformat=png
...                     },
...                 vcodec=copy
...                 }
...             :standard{
...                 access=file,
...                 dst=%(parent)s\\\\redirect.mp4
...                 }
...         \'\'\') % {
...             'stem': file_path.stem,
...             'parent': file_path.parent,
...             },
...         ])
... ''')
===== OK =====

Mutiline subscripts are not allowed.

>>> _check('''
...     qwe = asd[
...         'very long string key that does not fit a line']
... ''')
===== Violation =====
qwe = asd[
    'very long string key that does not fit a line']
    ^ X033
===== Not OK =====

Multiline type aliases are allowed, altough they are technically subscritps.

>>> _check('''
...     RequestDataType = Union[
...         LockMachineRequest,
...         ReleaseMachineRequest,
...         ]
...     ''')
===== OK =====
"""

import ast
from typing import Iterable
from typing import Sequence

from linter._display import ASTViolation
from linter._display import Start
from linter._display import _Code
from linter._display import print_violations
from linter._lines import extended
from linter._lines import extended_up
from linter._lines import is_multiline


def newlines_in_multiline(tree: ast.Module, lines: Sequence[str]):
    def visit_node(node: ast.AST):
        if isinstance(node, ast.expr) and not is_multiline(node):
            return
        elif isinstance(node, ast.Call):
            yield from validate_node_and_items(node, [
                *node.args,
                *[k.value for k in node.keywords],
                ])
            yield from visit_nodes(ast.iter_child_nodes(node))
        elif isinstance(node, ast.Constant):
            triple_quotes = ('"""', "'''", 'r"""', "r'''", 'b"""', "b'''")
            if lines[node.lineno - 1].startswith(triple_quotes, node.col_offset):
                pass
            elif lines[node.lineno - 1].endswith('(', None, node.col_offset):
                yield ASTViolation(Start(lines, node), _x031)
            elif node.lineno == extended_up(node, lines):
                yield ASTViolation(Start(lines, node), _x035)
            else:
                pass
        elif isinstance(node, ast.JoinedStr):
            if node.lineno == extended_up(node, lines):
                yield ASTViolation(Start(lines, node), _x035)
        elif isinstance(node, ast.FunctionDef):
            yield from validate_node_and_items(node, [
                *node.args.posonlyargs,
                *node.args.args,
                *([node.args.vararg] if node.args.vararg is not None else []),
                *node.args.kwonlyargs,
                *([node.args.kwarg] if node.args.kwarg is not None else []),
                ])
            yield from visit_nodes(node.decorator_list)
            yield from visit_nodes(node.body)
        elif isinstance(node, ast.Subscript):
            # Structure of Subscript may depend on Python version.
            if isinstance(node.slice, ast.Index):
                index = node.slice.value
                if isinstance(index, ast.Tuple):
                    yield from validate_node_and_items(node, index.elts)
                    yield from visit_nodes(index.elts)
                else:
                    yield ASTViolation(Start(lines, index), _x033)
            elif isinstance(node.slice, ast.Tuple):
                yield from validate_node_and_items(node, node.slice.elts)
                yield from visit_nodes(node.slice.elts)
            else:
                yield ASTViolation(Start(lines, node.slice), _x033)
        elif isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            yield from validate_node_and_items(node, node.elts)
            yield from visit_nodes(ast.iter_child_nodes(node))
        elif isinstance(node, ast.Dict):
            yield from validate_node_and_items(node, node.values)
            yield from visit_nodes(ast.iter_child_nodes(node))
        else:
            yield from visit_nodes(ast.iter_child_nodes(node))

    def visit_nodes(nodes: Iterable[ast.AST]):
        for node in nodes:
            yield from visit_node(node)

    def validate_node_and_items(n, items):
        if not items:
            return
        if not is_multiline(n):
            return
        if items[0].lineno == items[-1].end_lineno:
            # OK: All items in one line.
            return
        if extended(lines, items[-1]) == (n.lineno, n.end_lineno):
            # OK: The expression is multiline in the last item only.
            return
        if n.lineno == items[0].lineno:
            yield ASTViolation(Start(lines, items[0]), _x031)
        for i in range(len(items) - 1):
            upper = items[i]
            lower = items[i + 1]
            if is_multiline(upper) and not is_multiline(lower):
                # OK, if both multiline. If no violations found down the tree,
                # the "border" line is like "}, {".
                if upper.end_lineno == lower.lineno:
                    yield ASTViolation(Start(lines, lower), _x032)

    yield from visit_node(tree)


_x031 = "X031 No newline before first item of a multiline expression"
_x032 = "X032 No newline after a multiline item"
_x033 = "X033 Multiline subscript is not allowed"
_x035 = (
    "X035 Multiline string is not enclosed with "
    "parentheses or the opening parenthesis is not on a "
    "separate line")


def _check(code):
    """Shortcut for code in docstring."""
    code = _Code(code)
    print_violations(newlines_in_multiline(tree=code.tree(), lines=code.lines()))
