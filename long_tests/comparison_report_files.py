# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import re
import sys
from datetime import datetime
from enum import Enum
from enum import auto
from functools import lru_cache
from pathlib import Path
from traceback import format_exception
from typing import Any
from typing import Collection
from typing import Mapping
from typing import NamedTuple
from typing import Sequence
from typing import Union

from _internal.service_registry import elasticsearch
from directories import run_metadata
from long_tests._alerts import Alert
from long_tests._alerts import AlertsService
from long_tests._alerts import MailgunTransport
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

FULL_INFO_PAGE_ID = '3332014108'
SHORT_INFO_PAGE_ID = '3244130442'


def main(args: Sequence[str]) -> int:
    parsed_args = parse_args(args)
    page_id = FULL_INFO_PAGE_ID if parsed_args.all_types else SHORT_INFO_PAGE_ID
    message = {
        'type': 'comparison_files_report',
        'started_at': datetime.utcnow().isoformat(timespec='microseconds'),
        'run_ft_revision': run_metadata()['run_ft_revision'],
        'run_hostname': run_metadata()['run_hostname'],
        'confluence_page_id': page_id,
        }
    try:
        if parsed_args.all_types:
            measurements = load_measurements(query_all)
        else:
            measurements = load_measurements(query)
        if not measurements:
            raise RuntimeError("No results found")
        message['confluence_page_url'] = _Report(page_id, measurements).create()
        _generate_alerts(measurements, message['confluence_page_url'])
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


class _Report(ComparisonReportConfluence):

    # See: https://networkoptix.atlassian.net/wiki/spaces/SD/pages/2864185358

    def _build_document(self) -> Document:
        doc = Document()
        data = _ReportData(self._measurements_raw)
        doc.add_content(TextBlock("Stand configuration:"))
        doc.add_content(self._get_stand_info_block(
                data.stand['OS'], data.stand['CPU'], data.stand['RAM']))
        table = _TableBuilder(data.get_versions())
        doc.add_content(table.create('Analytics (motion + object)', data.get_analytics_motion_object_data()))
        doc.add_content(table.create('MKV (motion)', data.get_mkv_motion_data()))
        doc.add_content(table.create('MKV (motion + object)', data.get_mkv_motion_object_data()))
        doc.add_content(table.create('Motion (motion)', data.get_motion_data()))
        doc.add_content(table.create('Motion (motion + object)', data.get_motion_object_data()))
        doc.add_content(table.create('NXDB (motion)', data.get_nxdb_motion_data()))
        doc.add_content(table.create('NXDB (motion + object)', data.get_nxdb_motion_object_data()))
        doc.add_content(table.create('Object (motion)', data.get_db_motion_data()))
        doc.add_content(table.create('Object (motion + object)', data.get_db_motion_object_data()))
        doc.add_content(TextBlock("\n"))
        doc.add_content(self._get_builds_table(data.get_builds()))
        return doc


class _ReportLineData:

    _op_name = {'read': 'ReadFile', 'write': 'WriteFile'}

    def __init__(self, operation: str, type_measurement: str, filename: str):
        self._operation = operation
        self.type = type_measurement
        self.filename = filename
        self._values: dict[str, int] = {}

    def append(self, version: str, value: int):
        self._values[version] = self._values.get(version, 0) + value

    def as_str(self) -> str:
        return self._op_name[self._operation] + ': ' + self.filename

    def get_comparison_values(self, versions: Sequence[str]) -> Sequence['_ComparisonValue']:
        result = []
        value_prev = 0
        for ver in versions:
            value = self._values.get(ver, 0)
            result.append(
                _ComparisonValue(ver, value, _ComparisonState.from_values(value, value_prev)))
            value_prev = value
        return result

    def __hash__(self):
        return hash((self._operation, self.type, self.filename))

    def __eq__(self, other) -> bool:
        return (
                self._operation == other._operation and self.type == other.type
                and self.filename == other.filename
                )


class _ReportData:

    def __init__(self, measurements: Collection[Mapping[str, Any]]):
        one_measurement = next(iter(measurements))
        self.stand: dict[str, Union[str, int]] = one_measurement['stand']
        if one_measurement['OS'].startswith('ubuntu'):
            self.stand['OS'] = 'Ubuntu'
        elif one_measurement['OS'].startswith('win'):
            self.stand['OS'] = 'Windows'
        else:
            self.stand['OS'] = one_measurement['OS']
        self._raw_data = measurements
        self._lines: Sequence[_ReportLineData] = []

    def get_versions(self) -> Sequence[str]:
        return [b.version for b in self.get_builds()]

    @lru_cache
    def get_builds(self) -> list[BuildInfo]:
        builds = {BuildInfo.from_dict(m) for m in self._raw_data}
        return sorted(list(builds), key=lambda b: b.sorting_key)

    def get_analytics_motion_object_data(self) -> Sequence[_ReportLineData]:
        pattern = re.compile(r'analytics_.*\.bin')
        return [ln for ln in self._get_lines('comparison_files_with_object_detection') if pattern.search(ln.filename)]

    def get_mkv_motion_data(self) -> Sequence[_ReportLineData]:
        pattern = re.compile(r'.*\.mkv')
        return [ln for ln in self._get_lines('comparison_files') if pattern.search(ln.filename)]

    def get_mkv_motion_object_data(self) -> Sequence[_ReportLineData]:
        pattern = re.compile(r'.*\.mkv')
        return [ln for ln in self._get_lines('comparison_files_with_object_detection') if pattern.search(ln.filename)]

    def get_motion_data(self) -> Sequence[_ReportLineData]:
        pattern = re.compile(r'motion_.*\.bin')
        return [ln for ln in self._get_lines('comparison_files') if pattern.search(ln.filename)]

    def get_motion_object_data(self) -> Sequence[_ReportLineData]:
        pattern = re.compile(r'motion_.*\.bin')
        return [ln for ln in self._get_lines('comparison_files_with_object_detection') if pattern.search(ln.filename)]

    def get_nxdb_motion_data(self) -> Sequence[_ReportLineData]:
        pattern = re.compile(r'.*\.nxdb')
        return [ln for ln in self._get_lines('comparison_files') if pattern.search(ln.filename)]

    def get_nxdb_motion_object_data(self) -> Sequence[_ReportLineData]:
        pattern = re.compile(r'.*\.nxdb')
        return [ln for ln in self._get_lines('comparison_files_with_object_detection') if pattern.search(ln.filename)]

    def get_db_motion_data(self) -> Sequence[_ReportLineData]:
        pattern = re.compile(r'.*\.sqlite$')
        return [ln for ln in self._get_lines('comparison_files') if pattern.search(ln.filename)]

    def get_db_motion_object_data(self) -> Sequence[_ReportLineData]:
        pattern = re.compile(r'.*\.sqlite$')
        return [ln for ln in self._get_lines('comparison_files_with_object_detection') if pattern.search(ln.filename)]

    def _get_lines(self, data_type: str) -> Sequence[_ReportLineData]:
        if self._lines:
            return [ln for ln in self._lines if ln.type == data_type]
        all_data = {}
        for one_measure in self._raw_data:
            for one_metric in one_measure['measures']:
                filename = Path(one_metric['path']).name
                if filename.endswith('.mkv'):
                    filename = 'some_video_file.mkv'
                if filename.endswith('.nxdb'):
                    filename = 'some_database.nxdb'
                line = _ReportLineData(one_metric['operation'], one_measure['type'], filename)
                if line in all_data:
                    line = all_data[line]
                else:
                    all_data[line] = line
                line.append(one_measure['version'], one_metric['count'])
        self._lines = sorted(list(all_data.values()), key=lambda ln: ln.filename)
        return [ln for ln in self._lines if ln.type == data_type]


class _TableBuilder:

    def __init__(self, versions: Sequence[str]):
        self._versions = versions

    def create(self, header_name: str, data: Sequence['_ReportLineData']) -> Table:
        table = Table(1800)
        row = TableRow()
        row.add_header_cells([header_name], width=400)
        row.add_header_cells(self._versions)
        table.add_row(row)
        for line in data:
            table.add_row(self._build_row(line))
        return table

    def _build_row(self, line: '_ReportLineData') -> TableRow:
        # The purpose of the report is to show the difference between two versions. It is not
        # a problem for this report if one of the tests failed, so it does not need to mark
        # the cell with the state WRONG in a different color.
        color_of_state = {
            _ComparisonState.WRONG: None,
            _ComparisonState.NOT_CHANGED: None,
            _ComparisonState.BETTER: Color.GREEN.value,
            _ComparisonState.WORSE: Color.RED.value,
            }
        row = TableRow()
        row.add_header_cells([line.as_str()], align=Alignment.LEFT)
        for cell in line.get_comparison_values(self._versions):
            row.add_cells([cell.value], align=Alignment.RIGHT, background=color_of_state[cell.state])
        return row


class _ComparisonState(Enum):
    WRONG = auto()
    NOT_CHANGED = auto()
    BETTER = auto()
    WORSE = auto()

    @classmethod
    def from_values(cls, value: int, value_prev: int) -> '_ComparisonState':
        threshold = 0.5
        noticeable_change = threshold * value_prev
        if value == 0 or value_prev == 0:
            return _ComparisonState.WRONG  # The zero value means the test failed.
        elif value > value_prev + noticeable_change:
            return _ComparisonState.WORSE
        elif value < value_prev - noticeable_change:
            return _ComparisonState.BETTER
        else:
            return _ComparisonState.NOT_CHANGED

    def __str__(self) -> str:
        return self.name


class _ComparisonValue(NamedTuple):
    version: str
    value: int
    state: _ComparisonState


def _generate_alerts(measurements: Collection[Mapping[str, Any]], report_url: str):
    data = _ReportData(measurements)
    get_data_methods_map = {
        'Analytics (motion + object)': data.get_analytics_motion_object_data,
        'MKV (motion)': data.get_mkv_motion_data,
        'MKV (motion + object)': data.get_mkv_motion_object_data,
        'Motion (motion)': data.get_motion_data,
        'Motion (motion + object)': data.get_motion_object_data,
        'NXDB (motion)': data.get_nxdb_motion_data,
        'NXDB (motion + object)': data.get_nxdb_motion_object_data,
        'Object (motion)': data.get_db_motion_data,
        'Object (motion + object)': data.get_db_motion_object_data,
        }
    all_alerts = []
    for header, get_data_method in get_data_methods_map.items():
        for line in get_data_method():
            comparison_values = line.get_comparison_values(data.get_versions())
            bad_values = [value for value in comparison_values if value.state == _ComparisonState.WORSE]
            for value in bad_values:
                message = [
                    f'{header}: {line.as_str()} -> {value.state}',
                    f'Report url: {report_url}',
                    ]
                alert = Alert(line.type, datetime.utcnow(), '\n'.join(message), value.version)
                all_alerts.append(alert)
    alerts_service = AlertsService()
    alerts_service.produce_alerts('Alert: comparison files', all_alerts, MailgunTransport())


# We use text strings for queries as it is more convenient to copy them to the Elasticsearch Console
# for testing and then copy them back. Using dictionaries is inconvenient because the code style
# requires a comma after the last element, which is not allowed in JSON.
query = r"""
{
  "size": 10000,
  "query": {
    "bool": {
      "filter": [
        {"terms": {"type": ["comparison_files", "comparison_files_with_object_detection"]}},
        {"terms": {"installer_type": ["release", "private", "beta", "rc"]}},
        {"exists": {"field": "measures"}},
        {"range": {"test_duration_sec": {"gte": 1800}}}
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
        {"terms": {"type": ["comparison_files", "comparison_files_with_object_detection"]}},
        {"exists": {"field": "measures"}},
        {"range": {"test_duration_sec": {"gte": 1800}}}
      ]
    }
  }
}
"""

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    _logger = logging.getLogger(__name__)
    exit(main(sys.argv[1:]))
