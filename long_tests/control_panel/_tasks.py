# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from collections.abc import Sequence
from datetime import datetime
from datetime import timezone
from typing import Any

from _internal.service_registry import elasticsearch


def get_tasks_log() -> Sequence[dict[str, Any]]:
    result = elasticsearch.search('ft-measure-*', query)
    log = []
    for doc in result['hits']['hits']:
        data = doc['_source']
        started_at = datetime.fromisoformat(data['started_at']).replace(tzinfo=timezone.utc)
        finished_at = datetime.fromisoformat(data['finished_at']).replace(tzinfo=timezone.utc)
        installers_url = data.get('installers_url', '')
        installers_url_text = installers_url.replace('https://artifactory.us.nxteam.dev/artifactory/', '')
        line = {
            'type': data['type'],
            'category': 'report' if '_report' in data['type'] else 'test',
            'started_at': started_at.strftime('%Y-%m-%d %H:%M'),
            'finished_at': finished_at.strftime('%Y-%m-%d %H:%M'),
            'task_status': data.get('task_status', ''),
            'installers_url': installers_url,
            'installers_url_text': installers_url_text,
            'installer_type': data.get('installer_type', ''),
            'version': data.get('version', ''),
            'error': data.get('error', ''),
            'artifacts_url': data.get('artifacts_url', ''),
            '_id': doc['_id'],
            '_index': doc['_index'],
            'css_class': 'failed' if data.get('task_status') == 'Fail' else '',
            }
        log.append(line)
    return log


query = """
    {
      "size": 150,
      "sort": [
        {"started_at": {"order": "desc"}}
      ]
    }
"""
