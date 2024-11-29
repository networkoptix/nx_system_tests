# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import enum
import logging
import sys
from collections import Counter
from collections.abc import Collection
from collections.abc import Mapping
from collections.abc import Sequence
from datetime import datetime
from enum import Enum
from functools import lru_cache
from traceback import format_exception
from typing import Any
from typing import NamedTuple

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

FULL_INFO_PAGE_ID = '3332341794'
SHORT_INFO_PAGE_ID = '3227615234'


def main(args: Sequence[str]) -> int:
    parsed_args = parse_args(args)
    page_id = FULL_INFO_PAGE_ID if parsed_args.all_types else SHORT_INFO_PAGE_ID
    message = {
        'type': 'comparison_http_rtsp_report',
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
        return 0
    except Exception as exc:
        message['error'] = ''.join(format_exception(exc)).rstrip()
        message['task_status'] = 'Fail'
        raise
    finally:
        message['finished_at'] = datetime.utcnow().isoformat(timespec='microseconds')
        _logger.info('Send message to Elasticsearch: %s', message)
        elasticsearch.send_flush('ft-measure-{YYYY}', message)


class _ReportLineData:

    def __init__(self, protocol: str, method: str, path: str):
        self._protocol = protocol
        self._method = method
        self._path = path
        self._values = Counter()

    def add(self, version: str, value: int):
        self._values.update({version: value})

    def as_str(self) -> str:
        return f'{self._protocol} {self._method} {self._path}'

    def get_values(self) -> Sequence['_ComparisonValue']:
        values_iter = iter(self._values.items())
        ver, requests_count = next(values_iter)
        result = [_ComparisonValue(ver, requests_count, _ComparisonState.NOT_CHANGED)]
        for ver, requests_count in values_iter:
            state = _ComparisonState.from_values(requests_count, result[-1].count)
            result.append(_ComparisonValue(ver, requests_count, state))
        return result


class _ReportData:

    def __init__(self, measurements: Collection[Mapping[str, Any]]):
        one_measurement = next(iter(measurements))
        self.stand: dict[str, str | int] = one_measurement['stand']
        if one_measurement['OS'].startswith('ubuntu'):
            self.stand['OS'] = 'Ubuntu'
        elif one_measurement['OS'].startswith('win'):
            self.stand['OS'] = 'Windows'
        else:
            self.stand['OS'] = one_measurement['OS']
        self._raw_data = measurements

    def get_versions(self) -> Sequence[str]:
        return [b.version for b in self.get_builds()]

    @lru_cache
    def get_builds(self) -> list[BuildInfo]:
        builds = {BuildInfo.from_dict(m) for m in self._raw_data}
        return sorted(list(builds), key=lambda b: b.sorting_key)

    def get_lines(self) -> Sequence[_ReportLineData]:
        all_data = {}
        for one_measure in self._raw_data:
            for one_metric in one_measure['measures']:
                path = one_metric['path']
                line_key = (one_metric['protocol'], one_metric['method'], path)
                if line_key not in all_data:
                    all_data[line_key] = _ReportLineData(one_metric['protocol'], one_metric['method'], path)
                all_data[line_key].add(one_measure['version'], one_metric['count'])
        return sorted(list(all_data.values()), key=lambda ln: ln.as_str())


class _Report(ComparisonReportConfluence):

    # See: https://networkoptix.atlassian.net/wiki/spaces/SD/pages/2899542033

    def _build_document(self) -> Document:
        doc = Document()
        report_data = _ReportData(self._measurements_raw)
        doc.add_content(TextBlock("Stand configuration:"))
        doc.add_content(self._get_stand_info_block(
            report_data.stand['OS'], report_data.stand['CPU'], report_data.stand['RAM']))
        table = Table(1600)
        row = TableRow()
        row.add_header_cells(['Request'], width=600)
        row.add_header_cells(report_data.get_versions())
        table.add_row(row)
        color_map = {
            _ComparisonState.BETTER: Color.GREEN.value,
            _ComparisonState.WORSE: Color.RED.value,
            }
        for line in report_data.get_lines():
            row = TableRow()
            row.add_header_cells([line.as_str()], align=Alignment.LEFT)
            for value in line.get_values():
                row.add_cells(
                    [value.count], align=Alignment.CENTER, background=color_map.get(value.state))
            table.add_row(row)
        doc.add_content(table)
        doc.add_content(TextBlock("\n"))
        doc.add_content(self._get_builds_table(report_data.get_builds()))
        return doc


class _ComparisonState(Enum):
    NOT_CHANGED = enum.auto()
    BETTER = enum.auto()
    WORSE = enum.auto()

    @classmethod
    def from_values(cls, value: float, value_prev: float) -> '_ComparisonState':
        threshold = 0.5
        threshold_value = max(value, value_prev) * threshold
        value_diff = value - value_prev
        if abs(value_diff) <= threshold_value:
            return _ComparisonState.NOT_CHANGED
        elif value_diff > 0:
            return _ComparisonState.WORSE
        else:
            return _ComparisonState.BETTER


class _ComparisonValue(NamedTuple):
    version: str
    count: float
    state: _ComparisonState


query = r"""
{
  "size": 10000,
  "query": {
    "bool": {
      "filter": [
        {"term": {"type": "comparison_http_rtsp"}},
        {"terms": {"installer_type": ["release", "private", "beta", "rc"]}},
        {"exists": {"field": "measures"}},
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
        {"term": {"type": "comparison_http_rtsp"}},
        {"exists": {"field": "measures"}},
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
