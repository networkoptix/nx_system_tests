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

FULL_INFO_PAGE_ID = '3332177960'
SHORT_INFO_PAGE_ID = '3299868846'


def main(args: Sequence[str]) -> int:
    parsed_args = parse_args(args)
    page_id = FULL_INFO_PAGE_ID if parsed_args.all_types else SHORT_INFO_PAGE_ID
    message = {
        'type': 'comparison_ram_cpu_report',
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

    # See: https://networkoptix.atlassian.net/wiki/spaces/SD/pages/2945286198

    def _build_document(self) -> Document:
        doc = Document()
        report_data = _ReportData(self._measurements_raw)
        doc.add_content(TextBlock('Stand configuration:'))
        for os, config in report_data.get_stands().items():
            doc.add_content(self._get_stand_info_block(os, config['CPU'], config['RAM']))
        table = Table(1800)
        row = TableRow()
        row.add_header_cells([''])
        row.add_header_cells(report_data.get_versions(), colspan=2)
        table.add_row(row)
        row = TableRow()
        row.add_header_cells([''])
        row.add_header_cells(['CPU', 'RAM'] * len(report_data.get_versions()))
        table.add_row(row)
        color_map = {
            _ComparisonState.WORSE: Color.RED.value,
            _ComparisonState.BETTER: Color.GREEN.value,
            }
        for line in report_data.get_lines():
            row = TableRow()
            row.add_header_cells([line.os])
            for value in line.get_values():
                row.add_cells(
                    [f'{value.cpu:.2f}'], align=Alignment.CENTER, background=color_map.get(value.cpu_state))
                row.add_cells(
                    [f'{value.ram:.1f} Mb'], align=Alignment.CENTER, background=color_map.get(value.cpu_state))
            table.add_row(row)
        doc.add_content(table)
        doc.add_content(TextBlock("\n"))
        doc.add_content(self._get_builds_table(report_data.get_builds()))
        return doc


class _ReportLineData:

    def __init__(self, os: str, versions: Sequence[str]):
        self.os: str = os
        self._values: dict[str, tuple[float, float]] = dict.fromkeys(versions, (0, 0))

    def __hash__(self):
        return hash(self.os)

    def __eq__(self, other) -> bool:
        return self.os == other.os

    def set_value(self, version: str, cpu: float, ram: float):
        self._values[version] = (cpu, ram)

    def get_values(self) -> Sequence['_ComparisonValue']:
        values_iter = iter(self._values.items())
        ver, [cpu, ram] = next(values_iter)
        result = [_ComparisonValue(ver, cpu, _ComparisonState.NOT_CHANGED, ram, _ComparisonState.NOT_CHANGED)]
        for ver, [cpu, ram] in values_iter:
            cpu_state = _ComparisonState.from_values(cpu, result[-1].cpu)
            ram_state = _ComparisonState.from_values(ram, result[-1].ram)
            result.append(_ComparisonValue(ver, cpu, cpu_state, ram, ram_state))
        return result


class _ReportData:

    def __init__(self, measurements: Collection[Mapping[str, Any]]):
        self._raw_data = measurements

    def get_versions(self) -> Sequence[str]:
        return [b.version for b in self.get_builds()]

    def get_stands(self) -> Mapping[str, Any]:
        return {_define_os(m['OS']): m['stand'] for m in self._raw_data}

    @lru_cache
    def get_builds(self) -> list[BuildInfo]:
        builds = {BuildInfo.from_dict(m) for m in self._raw_data}
        return sorted(list(builds), key=lambda b: b.sorting_key)

    def get_lines(self) -> Sequence[_ReportLineData]:
        all_data = {}
        for one_measurements in self._raw_data:
            line = _ReportLineData(_define_os(one_measurements['OS']), self.get_versions())
            if line in all_data:
                line = all_data[line]
            else:
                all_data[line] = line
            cpu = one_measurements['cpu_mediaserver_usage']
            ram = one_measurements['ram_mediaserver_usage_mb']
            line.set_value(one_measurements['version'], cpu, ram)
        return sorted(list(all_data.values()), key=lambda ln: ln.os)


class _ComparisonState(Enum):
    WRONG = auto()
    NOT_CHANGED = auto()
    BETTER = auto()
    WORSE = auto()

    @classmethod
    def from_values(cls, value: float, value_prev: float) -> '_ComparisonState':
        threshold = 0.5
        diff = abs(value - value_prev)
        if value_prev == 0:
            return _ComparisonState.NOT_CHANGED
        elif value == 0:
            return _ComparisonState.WRONG
        elif value < value_prev and diff >= threshold * value_prev:
            return _ComparisonState.BETTER
        elif value > value_prev and diff >= threshold * value_prev:
            return _ComparisonState.WORSE
        else:
            return _ComparisonState.NOT_CHANGED


class _ComparisonValue(NamedTuple):
    version: str
    cpu: float
    cpu_state: '_ComparisonState'
    ram: float
    ram_state: '_ComparisonState'


def _generate_alerts(measurements: Collection[Mapping[str, Any]], report_url: str):
    all_alerts = []
    for line in _ReportData(measurements).get_lines():
        for value in line.get_values():
            messages = []
            if value.cpu_state == _ComparisonState.WORSE:
                messages.append(
                    f'{line.os}, {value.version}: CPU value {value.cpu}, state {value.cpu_state}')
            elif value.ram_state == _ComparisonState.WORSE:
                messages.append(
                    f'{line.os}, {value.version}: RAM value {value.ram}, state {value.ram_state}')
            if messages:
                messages.append(f'Report url: {report_url}')
                alert = Alert(
                    'comparison_ram_cpu', datetime.utcnow(), '\n'.join(messages), value.version)
                all_alerts.append(alert)
    alerts_service = AlertsService()
    alerts_service.produce_alerts('Alert: comparison CPU/RAM', all_alerts, MailgunTransport())


def _define_os(os_name: str) -> str:
    if os_name.startswith('ubuntu'):
        return 'Ubuntu'
    elif os_name.startswith('win'):
        return 'Windows'
    else:
        return os_name


# We use text strings for queries as it's more convenient to copy them to the Elasticsearch Console
# for testing and then copy them back. Using dictionaries is inconvenient because the code style
# requires a comma after the last element, which is not allowed in JSON.
query = r"""
{
  "size": 10000,
  "query": {
    "bool": {
      "filter": [
        {"term": {"type": "comparison_ram_cpu"}},
        {"exists": {"field": "ram_mediaserver_usage_mb"}},
        {"range": {"test_duration_sec": {"gte": 1800}}},
        {"terms": {"installer_type": ["release", "private", "beta", "rc"]}}
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
        {"term": {"type": "comparison_ram_cpu"}},
        {"exists": {"field": "ram_mediaserver_usage_mb"}},
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
