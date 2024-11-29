# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
"""Specialized differ for data returned by mediaserver methods.

>>> assert PathPattern('').match([])
>>> assert PathPattern('abc').match(['abc'])
>>> assert PathPattern('*').match(['abc'])
>>> assert PathPattern('abc/def/xyz').match(['abc', 'def', 'xyz'])
>>> assert PathPattern('abc/*/xyz').match(['abc', 'def', 'xyz'])
>>> assert not PathPattern('abc/*/xyz').match(['abc', 'def'])
>>> assert PathPattern('*/def/xyz').match(['abc', 'def', 'xyz'])
>>> assert PathPattern('abc/*def/xyz').match(['abc', 'typedef', 'xyz'])
>>> assert PathPattern('abc/*def/xyz').match(['abc', 'def', 'xyz'])
>>> assert not PathPattern('abc/def').match(['abc'])
>>> assert not PathPattern('').match(['abc'])
>>> assert not PathPattern('abc').match([])
>>> assert not PathPattern('abc').match(['abX'])
>>> assert not PathPattern('*').match(['abc', 'def'])
>>> assert not PathPattern('abc/def/xyz').match(['abc', 'deX', 'xyz'])
>>> assert not PathPattern('abc/*/xyz').match(['abX', 'def', 'xyz'])
>>> assert not PathPattern('*/def/xyz').match(['abc', 'def', 'xyX'])
>>> assert PathPattern('**').match(['abc', 'def', 'xyz'])
>>> assert PathPattern('abc/**').match(['abc', 'def', 'xyz'])
>>> assert PathPattern('abc/**').match(['abc', 'def'])
>>> assert PathPattern('abc/**').match(['abc'])
>>> assert not PathPattern('abc/def/**').match(['abc'])
>>> assert PathPattern('abc/def/**').match(['abc', 'def', 'xyz'])
>>> assert not PathPattern('abk/**').match(['abc', 'def', 'xyz'])
>>> assert not PathPattern('abc/def/**').match(['abc', 'deg', 'xyz'])
>>> PathPattern('**/abc')  # doctest: +ELLIPSIS
Traceback (most recent call last):
    ...
ValueError: ...
>>> PathPattern('abc/**/xyz')  # doctest: +ELLIPSIS
Traceback (most recent call last):
    ...
ValueError: ...
>>> DataDiffer('raw').diff([1, 2, 3, 4, 5], [1, 2, 10])  # doctest: +ELLIPSIS
[...Diff...2...change...3...10...Diff...length...]
>>> DataDiffer('raw').diff({'a': 1, 'b': 2, 'c': 3, 'd': 4}, {'a': 6, 'b': 2, 'c': 3, 'e': 5})  # doctest: +ELLIPSIS
[...Diff...remove...d...Diff...add...e...Diff...a...change...1...6...]
>>> DataDiffer('raw').diff({'a': {'b': {'c': 'abc'}}}, {'a': {'b': {'c': 'def'}}})  # doctest: +ELLIPSIS
[...Diff...a...b...c...changed...abc...def...]
>>> diff_list = [
...     Diff(['a', 'b', 'c'], 'int', 'changed', 0, 1),
...     Diff(['a', 'b', 'd'], 'str', 'changed', 'abc', 'def'),
...     ]
>>> assert whitelist_diffs(diff_list, []) == []
>>> assert whitelist_diffs(diff_list, [PathPattern('a/b/**')]) == diff_list
>>> assert whitelist_diffs(diff_list, [PathPattern('a/b/c')]) == diff_list[:-1]
>>> assert whitelist_diffs(diff_list, [PathPattern('a/b/d')]) == diff_list[1:]
>>> assert whitelist_diffs(diff_list, [PathPattern('a/b/c'), PathPattern('a/b/d')]) == diff_list
"""

import fnmatch
import json
import logging
import math
from collections import namedtuple
from itertools import zip_longest
from uuid import UUID

_logger = logging.getLogger(__name__)


def path2str(path):
    return '/'.join(map(str, path))


def _truncate_str(content, max_len):
    if len(content) > max_len:
        return content[:max_len] + '...'
    else:
        return content


class Diff:

    @staticmethod
    def list_to_str(diff_list):
        return '\n'.join(map(str, diff_list)) + '\n'

    def __init__(self, path, element_name, action, x=None, y=None, message=None):
        self.path = path
        self.element_name = element_name
        self.action = action
        self.x = x
        self.y = y
        self.message = message

    @property
    def _key(self):
        return (tuple(self.path), self.element_name, self.action, self.x, self.y)

    def __eq__(self, other):
        return self._key == other._key

    def __hash__(self):
        return hash(self._key)

    def __repr__(self):
        return '<Diff: {}>'.format(self)

    def __str__(self):
        return '/{}: {} {} (x={}, y={}): {}'.format(
            self.path_str,
            self.element_name or 'element',
            self.action,
            _truncate_str(repr(self.x), 100),
            _truncate_str(repr(self.y), 100),
            self.message or '',
            )

    @property
    def path_str(self):
        return path2str(self.path)


KeyInfo = namedtuple('KeyInfo', 'name key_elements name_elements')


class PathPattern:

    def __init__(self, pattern_str=None):
        self._pattern = pattern_str.split('/') if pattern_str else []
        if '**' in self._pattern[:-1]:
            raise ValueError("'**' is only allowed at the end of the pattern")

    def match(self, path):
        if not self._pattern and not path:
            return True
        for pattern, key in zip_longest(self._pattern, path):
            if pattern == '**':
                return True
            if key is None or pattern is None:
                # Either keys or pattern has ended
                return False
            if isinstance(key, int):
                if pattern == '*':  # Non-keyed list items are never matched by index in pattern
                    continue
                raise ValueError(
                    f"Pattern {self._pattern} assumes a dict or keyed list "
                    f"at the level of {pattern}, but it's a non-keyed list")
            if fnmatch.fnmatchcase(key, pattern):
                continue
            return False
        return True


class DataDiffer:

    def __init__(self, name, key_map=None):
        self.name = name
        self._key_map = key_map or []  # (PathPattern, KeyInfo) list

    def __str__(self):
        return self.name

    def diff(self, x, y, path=None):
        diff_data = self._diff(path or [], x, y)
        if diff_data:
            _logger.debug('Diff: %r', diff_data)
        return diff_data

    def _diff(self, path, x, y):
        _logger.debug('Diff: checking /%s: x=%r y=%r', path2str(path), x, y)
        approx_cls = _Approx
        if type(x) != type(y):
            if isinstance(x, approx_cls) or isinstance(y, approx_cls):
                try:
                    return self._diff_primitive(path, x, y)
                except TypeError:
                    pass  # Return 'Different element type...'
            x_type_name = type(x).__name__
            y_type_name = type(y).__name__
            message = 'Different element types: x has %s, y has %s' % (x_type_name, y_type_name)
            return [Diff(path, None, 'changed', x, y, message)]
        if isinstance(x, (list, tuple)):
            return self._diff_seq(path, x, y)
        if isinstance(x, dict):
            return self._diff_dict(path, x, y)
        if isinstance(x, str):
            # Some values in the mediaserver DB may be JSON-encoded structures,
            # which may differ in formatting (spaces between keys and values).
            try:
                x_json = json.loads(x)
                y_json = json.loads(y)
            except ValueError:
                pass  # Not an error: values are just strings, not JSON.
            else:
                return self._diff(path, x_json, y_json)
            return self._diff_primitive(path, x, y)
        # Up till now mediaserver return exactly same float values, hence no threshold.
        if isinstance(x, (int, bytes, float, UUID, approx_cls)):
            return self._diff_primitive(path, x, y)
        raise TypeError(f'Unsupported type {type(x)!r} of element {x!r}')

    def _diff_primitive(self, path, x, y):
        if x != y:
            message = 'x ({}) != y ({})'.format(
                _truncate_str(repr(x), 100),
                _truncate_str(repr(y), 100),
                )
            return [Diff(path, type(x).__name__, 'changed', x, y, message)]
        else:
            return []

    def _find_key_info(self, path):
        for pattern, key_info in self._key_map:
            if pattern.match(path):
                return key_info
        return None

    def _diff_seq(self, path, x, y):
        key_info = self._find_key_info(path)
        if key_info:
            return self._diff_keyed_seq(path, x, y, key_info)
        else:
            return self._diff_non_keyed_seq(path, x, y)

    def _diff_non_keyed_seq(self, path, x_seq, y_seq):
        result_diff_list = []
        for i, (x, y) in enumerate(zip(x_seq, y_seq)):
            diff_list = self._diff(path + [i], x, y)
            if diff_list:
                result_diff_list += diff_list
        if len(x_seq) != len(y_seq):
            message = (
                    'Sequence length does not match: '
                    'x has %d elements, y has %d'
                    % (len(x_seq), len(y_seq)))
            diff = Diff(path, 'sequence', 'changed', message=message)
            result_diff_list.append(diff)
        return result_diff_list

    def _diff_keyed_seq(self, path, x_seq, y_seq, key_info):

        def get_attr(element, path):
            value = element
            for attr in path.split('.'):
                value = value[attr]
            return value

        def element_key(element):
            key = [get_attr(element, attr) for attr in key_info.key_elements]
            if len(key_info.key_elements) > 1:
                return '|'.join(map(str, key))
            else:
                return key[0]

        def element_name(element):
            name = [get_attr(element, attr) for attr in key_info.name_elements]
            if len(name) > 1:
                return '|'.join(map(str, name))
            else:
                return name[0]

        diff_list = []
        x_dict = {element_key(element): element for element in x_seq}
        y_dict = {element_key(element): element for element in y_seq}
        for key in sorted(set(x_dict) - set(y_dict)):
            element = x_dict[key]
            diff_list.append(Diff(path, key_info.name, 'removed', element_name(element), None, element))
        for key in sorted(set(y_dict) - set(x_dict)):
            element = y_dict[key]
            diff_list.append(Diff(path, key_info.name, 'added', None, element_name(element), element))
        for key in sorted(set(x_dict) & set(y_dict)):
            name = element_name(x_dict[key])
            diff_list += self._diff(path + [name], x_dict[key], y_dict[key])
        return diff_list

    def _diff_dict(self, path, x_dict, y_dict):
        diff_list = []
        for key in sorted(set(x_dict) - set(y_dict)):
            diff_list.append(Diff(
                path, 'dict', 'removed', key, None, 'Element is removed: %s=%r' % (key, x_dict[key])))
        for key in sorted(set(y_dict) - set(x_dict)):
            diff_list.append(Diff(
                path, 'dict', 'added', None, key, 'Element is added: %s=%r' % (key, y_dict[key])))
        for key in sorted(set(x_dict) & set(y_dict)):
            diff_list += self._diff(path + [key], x_dict[key], y_dict[key])
        return diff_list


def log_diff_list(log_fn, diff_list):
    for diff in diff_list:
        log_fn('> %s', diff)


def whitelist_diffs(diff_list, whitelist):
    result = []
    for diff in diff_list:
        if any(pattern.match(diff.path) for pattern in whitelist):
            result.append(diff)
    return result


class _Approx:
    pass


class ApproxRel(_Approx):

    def __init__(self, value, tol):
        self._value = value
        self._tol = tol

    def __eq__(self, other):
        return math.isclose(other, self._value, rel_tol=self._tol)

    def __repr__(self):
        return '<{}: {}>'.format(self.__class__.__name__, self._value)


class ApproxAbs(_Approx):

    def __init__(self, value, tol):
        self._value = value
        self._tol = tol

    def __eq__(self, other):
        return math.isclose(other, self._value, abs_tol=self._tol)

    def __repr__(self):
        return '<{}: {}>'.format(self.__class__.__name__, self._value)
