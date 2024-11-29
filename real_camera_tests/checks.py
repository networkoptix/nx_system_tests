# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
from abc import ABCMeta
from abc import abstractmethod
from fnmatch import fnmatch
from traceback import format_tb
from typing import Collection
from typing import Mapping
from typing import Union

CODECS = {8: 'MJPEG', 28: 'H264', 'HEVC': 'H265', 'acc': 'ACC'}


class Result(metaclass=ABCMeta):

    @abstractmethod
    def is_success(self) -> bool:
        pass

    @abstractmethod
    def can_be_final(self) -> bool:
        pass

    @abstractmethod
    def is_skip(self) -> bool:
        pass

    @abstractmethod
    def get_text_result(self) -> str:
        pass

    def as_dict(self):
        return {
            'is_success': self.is_success(),
            'can_be_final': self.can_be_final(),
            'is_skip': self.is_skip(),
            'text_result': self.get_text_result(),
            }


def format_exception(exception):
    return (
        f"Python exception failure: {exception.__repr__()}\n"
        f"Traceback (most recent call last):\n"
        f"{''.join(format_tb(exception.__traceback__))}")


class PythonExceptionResult(Result):

    def __init__(self, exception: Exception):
        self._exception = exception

    def is_success(self) -> bool:
        return False

    def can_be_final(self) -> bool:
        return True

    def is_skip(self) -> bool:
        return False

    def get_text_result(self):
        return format_exception(self._exception)


class DictCompareResult(Result):

    def __init__(self, actual, expected, errors=()):
        self._actual = actual
        self._expected = expected
        self._errors = errors

    def is_success(self) -> bool:
        return False if self._errors else True

    def can_be_final(self) -> bool:
        return True

    def is_skip(self) -> bool:
        return False

    def get_text_result(self):
        result = [
            f"{self.__class__.__name__}: is a match: {self.is_success()}",
            f"Actual: {json.dumps(self._actual, indent=4)}",
            f"Expected: {json.dumps(self._expected, indent=4)}",
            ]
        if self._errors:
            result = [*result, "Errors:", *self._errors]
        return '\n'.join(result)


class _StringResult(Result, metaclass=ABCMeta):

    def __init__(self, info: Union[str, Collection, Mapping]):
        if not isinstance(info, str):
            # If info is not Json serializable the test must crash
            self._string = json.dumps(info, indent=4)
        else:
            self._string = info

    def get_text_result(self):
        return f"{self.__class__.__name__}: {self._string}"


class Halt(_StringResult):

    def __init__(self, info=""):
        super().__init__(info)

    def is_success(self) -> bool:
        return False

    def can_be_final(self) -> bool:
        return False

    def is_skip(self) -> bool:
        return False


class Skipped(_StringResult):

    def __init__(self, info=""):
        super().__init__(info)

    def is_success(self) -> bool:
        return False

    def can_be_final(self) -> bool:
        return True

    def is_skip(self) -> bool:
        return True


class Success(_StringResult):

    def __init__(self, info=""):
        super().__init__(info)

    def is_success(self) -> bool:
        return True

    def can_be_final(self) -> bool:
        return True

    def is_skip(self) -> bool:
        return False


class Failure(_StringResult):

    def __init__(self, info=""):
        super().__init__(info)

    def is_success(self) -> bool:
        return False

    def can_be_final(self) -> bool:
        return True

    def is_skip(self) -> bool:
        return False


class TimedOut(Result):

    def __init__(self, timeout, duration, last_result):
        self._timeout = timeout
        self._duration = duration
        self._last_result = last_result

    def is_success(self) -> bool:
        return False

    def can_be_final(self) -> bool:
        return True

    def is_skip(self) -> bool:
        return False

    def get_text_result(self) -> str:
        return '\n'.join([
            f"Timed out: {self._duration}/{self._timeout} sec",
            "Last available result:",
            self._last_result.get_text_result(),
            ])


class VideoCheckResult(Result):

    def __init__(self, raw_result, is_success: bool):
        self.raw_result = raw_result
        self._is_success = is_success

    def is_success(self) -> bool:
        return self._is_success

    # TODO: Verify if it is always so
    def can_be_final(self) -> bool:
        return True

    def is_skip(self) -> bool:
        return False

    def get_text_result(self):
        return self._make_result_table()

    def as_dict(self):
        result = {
            'raw_result': self.raw_result,
            **super().as_dict(),
            }
        return result

    @staticmethod
    def _stringify(value, rel_tolerance=None, abs_tolerance=None):
        if rel_tolerance is not None and value is not None:
            return f'{value:.1f} \N{PLUS-MINUS SIGN} {value * rel_tolerance:.1f}'
        if abs_tolerance is not None and value is not None:
            return f'{value:.1f} \N{PLUS-MINUS SIGN} {abs_tolerance:.1f}'
        if value is None:
            return '--'
        try:
            return f'{value:.1f}'
        except (ValueError, TypeError):
            return str(value)

    def _make_row(self, results):
        signs = {
            True: '\N{HEAVY CHECK MARK} ',
            False: '\N{HEAVY BALLOT X} ',
            None: '  '}
        return [
            self._stringify(results.get('stream')),
            signs[results.get('config_ok')] + self._stringify(
                results.get('config'),
                abs_tolerance=results.get('config_abs_tolerance')),
            signs[results.get('metrics_ok')] + self._stringify(
                results.get('metrics'),
                rel_tolerance=results.get('metrics_rel_tolerance'))]

    def _make_result_table(self):
        column_names = ['', 'stream', 'config', 'metrics']
        cell_values = [
            [param_name, *self._make_row(param_results)]
            for param_name, param_results in self.raw_result.items()]
        table = [column_names, *cell_values]
        cell_width = max(len(cell) for row in table for cell in row) + 1
        table_strings = [
            ' '.join(f'{c: <{cell_width}}' for c in row)
            for row in table]
        table_row_separator = '\n' + '-' * len(table_strings[0]) + '\n'
        return table_row_separator.join(table_strings)


def expect_values(expected, actual, *args, **kwargs):
    checker = Checker()
    checker.expect_values(expected, actual, *args, **kwargs)
    return checker.errors()


def _compare(expected, actual, syntax=None, float_abs_error=None):
    if not syntax:
        if float_abs_error is not None and isinstance(actual, float):
            return abs(expected - actual) <= float_abs_error
        return expected == actual

    if syntax in ('*', '?', 'fn'):
        return fnmatch(str(actual), str(expected))

    if syntax == 'case_insensitive':
        if isinstance(expected, str) and isinstance(actual, str):
            return expected.lower() == actual.lower()
        return expected == actual

    raise KeyError('Unsupported syntax: {}'.format(syntax))


class Checker:

    def __init__(self):
        self._errors = []
        self._actual_values = {}

    def add_error(self, error, *args):
        self._errors.append(str(error).format(*[repr(a) for a in args]))

    def add_actual_value(self, p, a):
        self._actual_values[p] = a

    def errors(self) -> Collection[str]:
        return self._errors

    def expect_values(self, expected, actual, path='camera', **kwargs):
        if actual is None and expected is not None:
            self.add_error('{} is not found, expected {}', path, expected)
            return not self._errors

        if isinstance(expected, dict):
            self.expect_dict(expected, actual, path, **kwargs)
            return not self._errors

        if isinstance(expected, list):
            self.add_actual_value(path, actual)
            if not actual == expected:
                self.add_error('{} is {}, expected {}', path, actual, expected)

            return not self._errors

        if not _compare(expected, actual, **kwargs):
            self.add_error('{} is {}, expected {}', path, actual, expected)

        self.add_actual_value(path, actual)
        return not self._errors

    def expect_dict(self, expected, actual, path='camera', **kwargs):
        actual_type = type(actual).__name__
        for key, expected_value in expected.items():
            if key.startswith('!'):
                key = key[1:]
                equal_position, dot_position = 0, 0
                full_path = '{}.<{}>'.format(path, key)
            else:
                equal_position = key.find('=') + 1
                dot_position = key.find('.') + 1
                full_path = '{}.{}'.format(path, key)

            if equal_position and (not dot_position or equal_position < dot_position):
                if not isinstance(actual, list):
                    self.add_error('{} is {}, expected a list', path, actual_type)
                    continue

                item = self._search_item(*key.split('=', 1), items=actual, **kwargs)
                if item:
                    self.expect_values(expected_value, item, '{}[{}]'.format(path, key), **kwargs)
                else:
                    self.add_error('{} does not have item with {}', path, key)

            elif dot_position and (not equal_position or dot_position < equal_position):
                base_key, sub_key = key.split('.', 1)
                self.expect_values({base_key: {sub_key: expected_value}}, actual, path, **kwargs)

            else:
                if not isinstance(actual, dict):
                    self.add_error('{} is {}, expected {}', path, actual_type, expected)
                else:
                    self.expect_values(
                        expected_value, self._get_key_value(key, actual), full_path, **kwargs)

    # These are values that may be different between VMS version, so we normalize them.
    _KEY_VALUE_FIXES = {
        'encoderIndex': {0: 'primary', 1: 'secondary'},
        'codec': CODECS,
        }

    @classmethod
    def _get_key_value(cls, key, values):
        value = values.get(key)
        try:
            return cls._KEY_VALUE_FIXES[key][value]
        except (KeyError, TypeError):
            return value

    @classmethod
    def _search_item(cls, key, value, items, **kwargs):
        for item in items:
            if _compare(value, str(cls._get_key_value(key, item)), **kwargs):
                return item


def _parse_resolution(resolution_str):
    try:
        return [int(dim) for dim in resolution_str.split('x')]
    except (ValueError, AttributeError):
        return [-1, -1]


def _is_config_resolution_ok(stream, config):
    config_width, config_height = _parse_resolution(config)
    width_ok = stream['width'] == config_width
    height_ok = stream['height'] == config_height
    return width_ok and height_ok


def _is_metrics_resolution_ok(stream, metrics):
    metrics_width, metrics_height = _parse_resolution(metrics)
    metrics_total_pixels = metrics_width * metrics_height
    stream_total_pixels = stream['width'] * stream['height'] * stream['stream_count']
    return stream_total_pixels == metrics_total_pixels


def _compare_with_tolerance(first, second, relative_tolerance=None, absolute_tolerance=None):
    if absolute_tolerance:
        return (second - absolute_tolerance) <= first <= (second + absolute_tolerance)
    return second * (1 - relative_tolerance) <= first <= second * (1 + relative_tolerance)


def check_stream_video_parameters(
        stream_params,
        config_params,
        metrics_params,
        check_metrics,
        is_generic_link,
        check_duration=False,
        ):
    config_fps_abs_tolerance = 1.5
    metrics_fps_rel_tolerance = .1
    bitrate_rel_tolerance = 0.2
    duration_abs_tolerance = 10  # It takes up to ~8 seconds for some cameras to start streaming
    result = {
        'codec': {
            'stream': stream_params['codec'],
            'config': config_params.codec,
            'config_ok': (
                CODECS.get(stream_params['codec'], stream_params['codec'])
                == config_params.codec)},
        'bitrate_kbps': {
            'stream': stream_params['bitrate_kbps'],
            'metrics': metrics_params.get('bitrate_kbps'),
            'metrics_ok': (
                None if not check_metrics else
                False if 'bitrate_kbps' not in metrics_params else
                _compare_with_tolerance(
                    stream_params['bitrate_kbps'] * stream_params['resolution']['stream_count'],
                    metrics_params['bitrate_kbps'],
                    relative_tolerance=bitrate_rel_tolerance)),
            'metrics_rel_tolerance': bitrate_rel_tolerance},
        'actual_fps': {
            'stream': stream_params['fps'],
            'config': config_params.fps,
            'config_ok': (
                None if config_params.fps is None else
                _compare_with_tolerance(
                    stream_params['fps'],
                    config_params.fps,
                    absolute_tolerance=config_fps_abs_tolerance)),
            'metrics': metrics_params.get('actual_fps'),
            'metrics_ok': (
                None if not check_metrics else
                False if 'actual_fps' not in metrics_params else
                _compare_with_tolerance(
                    stream_params['fps'],
                    metrics_params['actual_fps'],
                    relative_tolerance=metrics_fps_rel_tolerance)),
            'config_abs_tolerance': config_fps_abs_tolerance,
            'metrics_rel_tolerance': metrics_fps_rel_tolerance},
        'target_fps': {
            'config': config_params.fps,
            'metrics': metrics_params.get('target_fps'),
            'metrics_ok': (
                None if not check_metrics else
                None if config_params.fps is None else
                'target_fps' not in metrics_params if is_generic_link else
                config_params.fps == metrics_params.get('target_fps'))},
        'resolution': {
            'stream': '{stream_count}x{width}x{height}'.format(**stream_params['resolution']),
            'config': config_params.resolution,
            'config_ok': (
                _is_config_resolution_ok(
                    stream_params['resolution'], config_params.resolution)),
            'metrics': metrics_params.get('resolution'),
            'metrics_ok': (
                None if not check_metrics else
                False if 'resolution' not in metrics_params else
                _is_metrics_resolution_ok(
                    stream_params['resolution'], metrics_params['resolution']))},
        'duration_sec': {
            'stream': stream_params['duration_sec'],
            'config': config_params.export_duration_sec,
            'config_ok':
                # No need to impose "no longer than" limit on duration_sec
                None if not check_duration else (
                stream_params['duration_sec'] > (
                    config_params.export_duration_sec - duration_abs_tolerance)
                ),
            },
        }
    config_ok = all(data.get('config_ok') is not False for data in result.values())
    metrics_ok = all(data.get('metrics_ok') is not False for data in result.values())
    result_ok = True if config_ok and metrics_ok else False
    return result, result_ok
