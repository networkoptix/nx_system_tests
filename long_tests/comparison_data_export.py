# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import itertools
import json
import logging
from collections.abc import Mapping
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from _internal.service_registry import elasticsearch
from long_tests._comparison_reports import BuildInfo
from long_tests._google_sheet import GoogleAuthProvider
from long_tests._google_sheet import GoogleSheet


def main() -> int:
    sheet_id = {
        'comparison_files': '1TGg5j7BwMI3Acc1WDHoIX6hANF255XlMCdfKzH4cV0o',
        'comparison_ram_cpu': '1cTedj4JYGLD3MvbGo1Fxo4If9n-9BB8MJnewNNJAVnQ',
        'comparison_http_rtsp': '1qprldS5Px-jVW21ddTzlyPwhsalbsGdVeB4Vu_o0GgI',
        }
    google_credentials_file = Path('~/.config/.secrets/google_credential_comparison-tests.json').expanduser()
    google_credentials = json.loads(google_credentials_file.read_text())
    google_auth_provider = GoogleAuthProvider(google_credentials)
    google_sheet = GoogleSheet(google_auth_provider)
    result = elasticsearch.search('ft-measure-*', _build_query(['comparison_files', 'comparison_files_with_object_detection']))
    documents = [data['_source'] for data in result['hits']['hits']]
    prepared_data = _prepare_data_comparison_files(documents)
    google_sheet.write(sheet_id['comparison_files'], 'comparison_files_raw_data', 'A1', prepared_data)
    result = elasticsearch.search('ft-measure-*', _build_query(['comparison_ram_cpu']))
    documents = [data['_source'] for data in result['hits']['hits']]
    prepared_data = _prepare_data_comparison_cpu_ram(documents)
    google_sheet.write(sheet_id['comparison_ram_cpu'], 'comparison_cpu_ram_raw_data', 'A1', prepared_data)
    result = elasticsearch.search('ft-measure-*', _build_query(['comparison_http_rtsp']))
    documents = [data['_source'] for data in result['hits']['hits']]
    prepared_data = _prepare_data_comparison_http_rtsp(documents)
    google_sheet.write(
        sheet_id['comparison_http_rtsp'], 'comparison_http_rtsp_raw_data', 'A1', prepared_data)
    return 0


def _prepare_data_comparison_files(raw_data: Sequence[Mapping[str, Any]]) -> Sequence[Mapping[str, Any]]:
    def measurement_key(record: Mapping[str, Any]):
        return record['operation'], record['file']

    def is_actual_file(path: str) -> bool:
        for part_of_name in ['.log', 'info.txt', '.lock', '.sqlite-wal', '.sqlite-shm']:
            if part_of_name in path:
                return False
        return True

    result = []
    # The test may be run multiple times on the same version. Only the last one is of interest.
    processed_keys = set()
    for doc in sorted(raw_data, key=lambda rec: rec['started_at'], reverse=True):
        data_key = (doc['type'], doc['version'])
        if data_key in processed_keys:
            continue
        build_info = BuildInfo.from_dict(doc)
        for measuring in doc['measures']:
            if measuring['path'].endswith('.mkv'):
                measuring['file'] = 'MKV files'
            elif measuring['path'].endswith('.nxdb'):
                measuring['file'] = 'NXDB databases'
            else:
                measuring['file'] = Path(measuring['path']).name
        measurements = [rec for rec in doc['measures'] if is_actual_file(rec['path'])]
        measurements.sort(key=measurement_key)
        for [_, group_iter] in itertools.groupby(measurements, key=measurement_key):
            group = list(group_iter)
            result.append({
                'type': doc['type'],
                'version': doc['version'],
                'operation': group[0]['operation'],
                'file': group[0]['file'],
                'count': sum((rec['count'] for rec in group)),
                'sorting_key': build_info.sorting_key,
                })
        processed_keys.add(data_key)
    return sorted(result, key=lambda rec: rec['sorting_key'])


def _prepare_data_comparison_cpu_ram(raw_data: Sequence[Mapping[str, Any]]) -> Sequence[Mapping[str, Any]]:
    result = []
    # The test may be run multiple times on the same version. Only the last one is of interest.
    processed_keys = set()
    for doc in sorted(raw_data, key=lambda rec: rec['started_at'], reverse=True):
        data_key = (doc['type'], doc['version'], doc['OS'])
        if data_key in processed_keys:
            continue
        build_info = BuildInfo.from_dict(doc)
        result.append({
            'type': doc['type'],
            'version': doc['version'],
            'OS': doc['OS'],
            'ram_mediaserver_usage_mb': doc['ram_mediaserver_usage_mb'],
            'ram_total_usage_mb': doc['ram_total_usage_mb'],
            'cpu_mediaserver_usage': doc['cpu_mediaserver_usage'],
            'cpu_total_usage': doc['cpu_total_usage'],
            'sorting_key': build_info.sorting_key,
            })
        processed_keys.add(data_key)
    return sorted(result, key=lambda rec: rec['sorting_key'])


def _prepare_data_comparison_http_rtsp(raw_data: Sequence[Mapping[str, Any]]) -> Sequence[Mapping[str, Any]]:
    result = []
    # The test may be run multiple times on the same version. Only the last one is of interest.
    processed_keys = set()
    for doc in sorted(raw_data, key=lambda rec: rec['started_at'], reverse=True):
        data_key = (doc['type'], doc['version'], doc['OS'])
        if data_key in processed_keys:
            continue
        if int(doc['test_duration_sec']) < 1800:
            continue
        build_info = BuildInfo.from_dict(doc)
        for measure in doc['measures']:
            result.append({
                'type': doc['type'],
                'version': doc['version'],
                'OS': doc['OS'],
                'method': measure['method'],
                'path': measure['path'],
                'protocol': measure['protocol'],
                'count': measure['count'],
                'sorting_key': build_info.sorting_key,
                })
        processed_keys.add(data_key)
    return sorted(result, key=lambda rec: rec['sorting_key'])


def _build_query(record_types: list) -> str:
    query_get_data = {
        "size": 10000,
        "query": {
            "bool": {
                "filter": [
                    {
                        "terms": {
                            "type": record_types,
                            },
                        },
                    {
                        "term": {
                            "task_status.keyword": "Success",
                            },
                        },
                    ],
                },
            },
        }
    return json.dumps(query_get_data, default=repr)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    _logger = logging.getLogger(__name__)
    exit(main())
