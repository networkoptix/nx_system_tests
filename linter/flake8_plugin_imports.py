# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import ast
import re
import tokenize
from ast import Assign
from ast import Constant
from ast import Import
from ast import ImportFrom
from ast import List
from ast import Module
from ast import Name
from ast import Set
from ast import Tuple


def one_import_per_line(logical_line, tokens):
    """Enforce one import per line.

    Diffs are simpler.
    Adding an import is always +1 in diff.
    Removing an import is always -1.
    Merge conflicts in within import are less likely and easier to resolve.

    When several names combined in a single import are reformatted,
    it produces extra diff, which may lead to more merge conflicts.
    Such reformatting may be caused by one added imported name,
    which does not fit the line width.

    Many names in a single import statement are often cumbersome.
    Formatting rules for this case are complicated.

    It's easier to refactor with regexes.

    It's easier to add, remove and reorder imports by editing line by line.

    PyCharm does not reformat names within parentheses in 'from' imports.

    PyCharm supports this style; it has a special setting for it.
    """
    s = ''.join(
        'f' if t.type == tokenize.NAME and t.string == 'from' else
        'i' if t.type == tokenize.NAME and t.string == 'import' else
        '(' if t.type == tokenize.OP and t.string == '(' else
        ')' if t.type == tokenize.OP and t.string == ')' else
        ',' if t.type == tokenize.OP and t.string == ',' else
        '.' if t.type == tokenize.OP and t.string == '.' else
        '' if t.type == tokenize.NL else
        'n' if t.type == tokenize.NAME else
        '_'
        for t in tokens)
    if re.match(r'f[n.]+i(n,|\(n)', s):
        yield 1, "X007 Imports must be formatted one name per line"


def no_relative_imports(tree: Module):
    for statement in tree.body:
        if isinstance(statement, ast.ImportFrom):
            if statement.level > 0:
                yield (
                    statement.lineno,
                    statement.col_offset,
                    "X008 Relative imports are prohibited",
                    None)


def blank_lines(tree, file_tokens):
    s = ''.join(
        'i' if t.type == tokenize.NAME and t.string == 'from' else
        'i' if t.type == tokenize.NAME and t.string == 'import' else
        'c' if t.type == tokenize.NAME and t.string == 'class' else
        'c' if t.type == tokenize.NAME and t.string == 'def' else
        'c' if t.type == tokenize.NAME and t.string == 'async' else
        'x' if t.type == tokenize.NAME else
        ';' if t.type == tokenize.NEWLINE else
        ',' if t.type == tokenize.NL else
        '_'
        for t in file_tokens)
    for m in re.finditer(r'i\w+;,,+x', s):
        line, offset = file_tokens[m.start()].start
        yield line, offset, "X010 Imports and module variables must be delimited by one blank line", None
    for m in re.finditer(r'i\w+;,,+i', s):
        line, offset = file_tokens[m.start()].start
        yield line, offset, "X011 Imports must be delimited by zero or one blank line", None


def no_from_imports(tree: Module):
    """Enforce basic 'import' statements to avoid module namespace pollution.

    Names like 'shutil.copy' or 'os.path' would become 'copy' and 'path'.
    Such names can be easily overwritten by a local variable or function.
    Moreover, they would lose any context.

    Some modules are traditionally imported in this form, e.g. 'import os'.

    Names from some other modules are rarely used throughout the file.
    Therefore, it makes no sense to save symbols with the 'from' form.

    Human perception is easier when a particular module is always imported the
    same way throughout the whole project.
    """
    for entry in tree.body:
        if isinstance(entry, ImportFrom):
            if entry.module in {'asyncio', 'os', 'hashlib', 'time', 'shutil', 'logging', 'random', 'json', 'shlex', 'tokenize', 'unittest'}:
                yield entry.lineno, 0, f"X022 The {entry.module!r} module may only be imported as 'import {entry.module}'", None


def only_from_imports(tree: Module):
    """Enforce the 'from' form to save keystrokes and minimize noise.

    Some names are quite unique; their module names can be safely omitted,
    which is especially valuable, if names are frequently used. For example:
    'datetime', 'timedelta', 'contextmanager', 'abstractmethod'.

    Human perception is easier when a particular module is always imported the
    same way throughout the whole project.
    """
    for entry in tree.body:
        if isinstance(entry, Import):
            for alias in entry.names:
                if alias.name in {'datetime', 'typing', 'contextlib', 'abc', 'uuid'}:
                    yield entry.lineno, 0, f"X023 The {alias.name !r} module may only be imported as 'from {alias.name} import ...'", None


def no_import_logger(tree: Module):
    """When moving functions, PyCharm does this."""
    for entry in tree.body:
        if isinstance(entry, ImportFrom):
            for alias in entry.names:
                if alias.name == '_logger':
                    yield entry.lineno, 0, "X024 A _logger object must be defined in each module", None


def sort_init_all(tree: Module):
    for entry in tree.body:
        if isinstance(entry, Assign):
            try:
                [target] = entry.targets
            except ValueError:
                pass
            else:
                if isinstance(target, Name) and target.id == '__all__':
                    if isinstance(entry.value, (List, Tuple, Set)):
                        if entry.value.elts != sorted(entry.value.elts, key=lambda v: v.value if isinstance(v, Constant) else None):
                            yield entry.lineno, 0, "X025 Entries in __all__ must be sorted", None
