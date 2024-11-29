# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import sys
from datetime import datetime
from enum import Enum
from enum import auto
from functools import lru_cache
from traceback import format_exception
from typing import Any
from typing import Collection
from typing import Mapping
from typing import NamedTuple
from typing import Sequence

from _internal.service_registry import elasticsearch
from directories import run_metadata
from long_tests._comparison_reports import BuildInfo
from long_tests._comparison_reports import ComparisonReportConfluence
from long_tests._comparison_reports import load_measurements
from long_tests._comparison_reports import parse_args
from long_tests.confluence import Alignment
from long_tests.confluence import Color
from long_tests.confluence import Document
from long_tests.confluence import Table
from long_tests.confluence import TableRow
from long_tests.confluence import TextBlock

FULL_INFO_PAGE_ID = '3332571171'
SHORT_INFO_PAGE_ID = '3278962790'


def main(args: Sequence[str]):
    parsed_args = parse_args(args)
    page_id = FULL_INFO_PAGE_ID if parsed_args.all_types else SHORT_INFO_PAGE_ID
    message = {
        'type': 'comparison_maximum_recorded_cameras_report',
        'started_at': datetime.utcnow().isoformat(timespec='microseconds'),
        'run_ft_revision': run_metadata()['run_ft_revision'],
        'run_hostname': run_metadata()['run_hostname'],
        'confluence_page_id': page_id,
        }
    try:
        if parsed_args.all_types:
            measurements = load_measurements(query_all, ['OS'])
        else:
            measurements = load_measurements(query, ['OS'])
        if not measurements:
            raise RuntimeError("No results found")
        message['confluence_page_url'] = _Report(page_id, measurements).create()
        message['task_status'] = 'Success'
    except Exception as exc:
        message['error'] = ''.join(format_exception(exc)).rstrip()
        message['task_status'] = 'Fail'
        raise
    finally:
        message['finished_at'] = datetime.utcnow().isoformat(timespec='microseconds')
        _logger.info("Send message to Elasticsearch: %s", message)
        elasticsearch.send_flush('ft-measure-{YYYY}', message)


class _Report(ComparisonReportConfluence):

    # See: https://networkoptix.atlassian.net/wiki/spaces/SD/pages/2945482753

    def _build_document(self) -> Document:
        doc = Document()
        report_data = _ReportData(self._measurements_raw)
        doc.add_content(TextBlock('Stand configuration:'))
        for os, config in report_data.get_stands().items():
            doc.add_content(self._get_stand_info_block(os, config['CPU'], config['RAM']))
        table = Table(1200)
        row = TableRow()
        row.add_header_cells(['OS', *report_data.get_versions()])
        table.add_row(row)
        for line in report_data.get_lines():
            row = TableRow()
            row.add_header_cells([line.os])
            for value in line.get_values():
                background = Color.YELLOW.value if value.state == _ComparisonState.CHANGED else None
                cell_value = value.as_str() if value is not None else ''
                row.add_cells([cell_value], align=Alignment.CENTER, background=background)
            table.add_row(row)
        doc.add_content(table)
        doc.add_content(TextBlock('\n'))
        doc.add_content(self._get_builds_table(report_data.get_builds()))
        return doc


class _ReportLineData:

    def __init__(self, os: str, versions: Sequence[str]):
        self.os = os
        self._raw_data: dict[str, tuple[int, int]] = dict.fromkeys(versions, (0, 0))

    def set_value(self, version: str, value1: int, value2: int):
        self._raw_data[version] = (value1, value2)

    def get_values(self) -> Sequence['_ComparisonValue']:
        data_iter = iter(self._raw_data.items())
        ver, [value1, value2] = next(data_iter)
        result = [_ComparisonValue(ver, value1, value2, _ComparisonState.NOT_CHANGED)]
        for ver, [value1, value2] in data_iter:
            state = _ComparisonState.from_values(value1, result[-1].value1, value2, result[-1].value2)
            result.append(_ComparisonValue(ver, value1, value2, state))
        return result


class _ReportData:

    def __init__(self, measurements: Collection[Mapping[str, Any]]):
        self._raw_data = measurements

    def get_versions(self) -> Sequence[str]:
        return [b.version for b in self.get_builds()]

    @lru_cache
    def get_builds(self) -> list[BuildInfo]:
        builds = {BuildInfo.from_dict(m) for m in self._raw_data}
        return sorted(list(builds), key=lambda b: b.sorting_key)

    def get_stands(self) -> Mapping[str, Any]:
        return {_define_os(measurement['OS']): measurement['stand'] for measurement in self._raw_data}

    def get_lines(self):
        all_data = {}
        for measurement in self._raw_data:
            os_name = _define_os(measurement['OS'])
            if os_name not in all_data:
                all_data[os_name] = _ReportLineData(os_name, self.get_versions())
            line = all_data[os_name]
            line.set_value(
                measurement['version'], int(measurement['pass1']), int(measurement['pass2']))
        return sorted(all_data.values(), key=lambda ln: ln.os)


class _ComparisonState(Enum):
    WRONG = auto()
    NOT_CHANGED = auto()
    CHANGED = auto()

    @staticmethod
    def from_values(
            value1: int, value1_prev: int, value2: int, value2_prev: int) -> '_ComparisonState':
        threshold = 0.25
        threshold_value1 = max(value1, value1_prev) * threshold
        threshold_value2 = max(value2, value2_prev) * threshold
        if value1 == 0 or value2 == 0:
            return _ComparisonState.WRONG
        elif value1_prev == 0 and value2_prev == 0:
            return _ComparisonState.NOT_CHANGED
        elif abs(value1 - value1_prev) < threshold_value1 and abs(value2 - value2_prev) < threshold_value2:
            return _ComparisonState.NOT_CHANGED
        else:
            return _ComparisonState.CHANGED


class _ComparisonValue(NamedTuple):

    version: str
    value1: int
    value2: int
    state: _ComparisonState

    def as_str(self) -> str:
        if self.value1 == 0 and self.value2 == 0:
            return ''
        else:
            return f'{self.value1}/{self.value2}'


def _define_os(os_name: str) -> str:
    if os_name.startswith('ubuntu'):
        return 'Ubuntu'
    elif os_name.startswith('win'):
        return 'Windows'
    else:
        return os_name


# We use text strings for queries as it is more convenient to copy them to the Elasticsearch Console
# for testing and then copy them back. Using dictionaries is inconvenient because the code style
# requires a comma after the last element, which is not allowed in JSON.
query = r"""
{
  "size": 10000,
  "query": {
    "bool": {
      "filter": [
        {"term": {"type": "comparison_maximum_recorded_cameras"}},
        {"terms": {"installer_type": ["release", "private", "beta", "rc"]}},
        {"exists": {"field": "pass1" }},
        {"range" : {"test_duration_sec": {"gte" : 1800}}}
     ]
    }
  }
}
"""

query_all = r"""
{
  "size": 10000,
  "query": {
    "bool": {
      "filter": [
        {"term": {"type": "comparison_maximum_recorded_cameras"}},
        {"exists": {"field": "pass1" }},
        {"range" : {"test_duration_sec": {"gte" : 1800}}}
     ]
    }
  }
}
"""


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    _logger = logging.getLogger(__name__)
    exit(main(sys.argv[1:]))
