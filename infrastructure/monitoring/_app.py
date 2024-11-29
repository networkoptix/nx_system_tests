# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
import logging
from fnmatch import fnmatch
from functools import partial
from http import HTTPStatus
from pathlib import Path
from typing import Sequence
from urllib.parse import parse_qs
from urllib.parse import urlparse

from infrastructure._http import App
from infrastructure._http import HTTPMethod
from infrastructure._http import MethodHandler
from infrastructure._http import StaticFilesHandler
from infrastructure._http import XSLTemplateHandler
from infrastructure._message_broker_config import get_monitoring_client
from infrastructure.monitoring._streams import StreamStateStore
from infrastructure.monitoring._systemd_service import CommandProxyError
from infrastructure.monitoring._systemd_service import list_services
from infrastructure.monitoring._task import TaskStore
from infrastructure.monitoring._worker import WorkerStateStore


def make_app():
    name = "FT Monitoring"
    message_broker = get_monitoring_client()
    app_root_path = Path(__file__).parent
    return partial(App, handlers=[
        _ListTasks(name, TaskStore(
            message_broker.get_batch_reader('ft:gitlab_job_updates', 40000),
            message_broker.get_batch_reader('ft:ft_view_job_updates', 40000),
            )),
        _ListStreams(name, StreamStateStore(message_broker)),
        _ListConsumers(name, StreamStateStore(message_broker)),
        _ListWorkers(name, WorkerStateStore(
            message_broker.get_batch_reader('ft:worker_state_updates', 20000))),
        _ConsumerMessage(name, StreamStateStore(message_broker)),
        _BatchesFTRedirect(),
        _ListServiceState(),
        _BaseIndexPage(name, sorted([_ListServiceState.url(), _ListTasks.url(), _ListWorkers.url(), _ListStreams.url()])),
        StaticFilesHandler(app_root_path, relative_paths=[
            '/templates/index.xsl',
            '/templates/worker_list.xsl',
            '/templates/task_list.xsl',
            '/templates/task.css',
            '/templates/table.css',
            '/templates/streams.css',
            '/templates/workers.css',
            '/templates/services.xsl',
            '/templates/services.css',
            '/templates/streams_sort.js',
            '/templates/streams.xsl',
            '/templates/consumers.xsl',
            '/templates/consumer_message.xsl',
            ]),
        ])


class _ListTasks(XSLTemplateHandler):
    _path = '/tasks/'
    _method = HTTPMethod.GET

    def __init__(self, app_name: str, task_store: TaskStore):
        super().__init__('/templates/task_list.xsl')
        self._app_name = app_name
        self._task_store = task_store

    def _handle(self, request):
        query = parse_qs(urlparse(request.path).query)
        task_sources = query.get('source', ['*'])
        task_groups = self._task_store.list()
        requested_groups = query.get('group', sorted(task_groups.keys()))
        # Limit amount of tasks per page so page could load over slow connections.
        task_group_quota = 5000 if len(requested_groups) == 1 else 10
        task_tables = []
        try:
            [task_source] = task_sources
        except ValueError:
            request.send_error(HTTPStatus.BAD_REQUEST.value)
            return
        for task_group in requested_groups:
            tasks = task_groups.get(task_group, [])
            tasks = [task for task in tasks if fnmatch(task.source(), task_source)]
            tasks = tasks[:task_group_quota]
            task_tables.append({
                "name": task_group,
                "href": self.url(('group', task_group)),
                "tasks": [task.serialize() for task in tasks],
                })
        tasks_data = {
            "app_name": self._app_name,
            "task_tables": task_tables,
            }
        self._send_template_data(request, tasks_data)


class _ListWorkers(XSLTemplateHandler):
    _path = '/workers/'
    _method = HTTPMethod.GET

    def __init__(self, app_name: str, worker_state_store: WorkerStateStore):
        super().__init__('/templates/worker_list.xsl')
        self._app_name = app_name
        self._worker_state_store = worker_state_store

    def _handle(self, request):
        query = parse_qs(urlparse(request.path).query)
        groups = query.get('group', [])
        try:
            [group_name] = groups
            worker_states = {group_name: self._worker_state_store.list().get(group_name, [])}
        except ValueError:
            worker_states = self._worker_state_store.list()
        groups_list = []
        for group, states in worker_states.items():
            groups_list.append({
                "group_id": group,
                "tasks_url": _ListTasks.url(('group', group)),
                "states": [state.serialize() for state in states],
                })
        workers_data = {
            "app_name": self._app_name,
            "groups": groups_list,
            }
        self._send_template_data(request, workers_data)


class _ListStreams(XSLTemplateHandler):
    _path = '/streams/'
    _method = HTTPMethod.GET

    def __init__(self, app_name: str, stream_state_store: StreamStateStore):
        super().__init__('/templates/streams.xsl')
        self._app_name = app_name
        self._stream_state_store = stream_state_store

    def _handle(self, request):
        stream_states = self._stream_state_store.list()
        groups_data = []
        for (stream, group), state in stream_states.items():
            groups_data.append({
                "stream_id": stream,
                "group_data": state.serialize(),
                "group_href": _ListConsumers.url(('stream', stream), ('group', group)),
                })
        self._send_template_data(request, {"app_name": self._app_name, 'groups': groups_data})


class _ListConsumers(XSLTemplateHandler):
    _path = '/consumers/'
    _method = HTTPMethod.GET

    def __init__(self, app_name: str, stream_state_store: StreamStateStore):
        super().__init__('/templates/consumers.xsl')
        self._app_name = app_name
        self._stream_state_store = stream_state_store

    def _handle(self, request):
        query = urlparse(request.path).query
        parsed_query = parse_qs(query)
        try:
            stream_states = self._list_stream_states(parsed_query)
        except _InvalidQuery:
            request.send_error(HTTPStatus.BAD_REQUEST.value)
            return
        consumers_data = []
        for (stream, group), state in stream_states.items():
            consumer_data = []
            for consumer in state.consumers():
                pending_messages = [{
                    'message_id': pending['message_id'],
                    'href': (_ConsumerMessage.url(('stream', stream), ('message', pending['message_id']))),
                    } for pending in consumer.pending()]
                consumer_data.append({**consumer.serialize(), 'pending': pending_messages})
            consumers_data.append({
                "stream_id": stream,
                "group_id": group,
                "consumers": consumer_data,
                })
        self._send_template_data(request, {"app_name": self._app_name, 'groups': consumers_data})

    def _list_stream_states(self, query):
        streams_states = self._stream_state_store.list()
        streams = query.get('stream', [])
        groups = query.get('group', [])
        if streams and groups:
            if len(streams) * len(groups) > 1:
                raise _InvalidQuery("Multiple streams and groups are not supported")
            consumer_filter = (streams[0], groups[0])
            if consumer_filter not in streams_states.keys():
                raise _InvalidQuery("Stream or group not found")
            return {consumer_filter: streams_states[consumer_filter]}
        else:
            return streams_states


class _ConsumerMessage(XSLTemplateHandler):
    _path = '/consumer-message/'
    _method = HTTPMethod.GET

    def __init__(self, app_name: str, stream_state_store: StreamStateStore):
        super().__init__('/templates/consumer_message.xsl')
        self._app_name = app_name
        self._stream_state_store = stream_state_store

    def _handle(self, request):
        query = parse_qs(urlparse(request.path).query)
        try:
            [stream_name] = query['stream']
            [message_id] = query['message']
        except ValueError:
            request.send_error(HTTPStatus.BAD_REQUEST.value)
            return
        message = self._stream_state_store.get_message(stream_name, message_id)
        try:
            formatted_message = json.dumps(message, indent=2)
        except ValueError:
            _logger.info("Message is not a JSON: %s", message)
            formatted_message = message
        streams_data = {
            "app_name": self._app_name,
            "message": formatted_message,
            }
        self._send_template_data(request, streams_data)


class _ListServiceState(XSLTemplateHandler):
    _path = '/services/'
    _method = HTTPMethod.GET

    def __init__(self):
        super().__init__('/templates/services.xsl')

    def _handle(self, request):
        command_proxy_urls = [
            'http://sc-ft003:8060/',
            'http://sc-ft004:8060/',
            'http://sc-ft005:8060/',
            'http://sc-ft006:8060/',
            'http://sc-ft007:8060/',
            'http://sc-ft008:8060/',
            'http://sc-ft009:8060/',
            'http://sc-ft010:8060/',
            'http://sc-ft011:8060/',
            'http://sc-ft012:8060/',
            'http://sc-ft013:8060/',
            'http://sc-ft014:8060/',
            'http://sc-ft015:8060/',
            'http://sc-ft016:8060/',
            'http://sc-ft017:8060/',
            'http://sc-ft018:8060/',
            'http://sc-ft019:8060/',
            'http://sc-ft020:8060/',
            'http://sc-ft021:8060/',
            'http://sc-ft022:8060/',
            'http://sc-ft023:8060/',
            'http://sc-ft024:8060/',
            ]
        hosts = [urlparse(url).hostname for url in command_proxy_urls]
        services = list_services(command_proxy_urls)
        template_data = {'services': [], 'failed_hosts': []}
        for host, host_data in zip(hosts, services):
            if isinstance(host_data, CommandProxyError):
                template_data['failed_hosts'].append(f'{host}: {host_data}')
                continue
            for raw in host_data:
                service = {
                    'host': host,
                    'id': raw['Id'],
                    'state': f'{raw["ActiveState"]}/{raw["SubState"]}',
                    'since': raw['StateChangeTimestamp'],
                    'upheld_by': raw['upheld_by'],
                    'health': raw['health'],
                    }
                if 'ExecStart' in raw:
                    service['ExecStart'] = f'ExecStart={raw["ExecStart"]}'
                if 'Triggers' in raw:
                    service['Triggers'] = f'Triggers={raw["Triggers"]}'
                if 'TimersCalendar' in raw:
                    service['TimersCalendar'] = f'TimersCalendar={raw["TimersCalendar"]}'
                template_data['services'].append(service)
        self._send_template_data(request, template_data)


class _BaseIndexPage(XSLTemplateHandler):
    _path = '/'
    _method = HTTPMethod.GET

    def __init__(self, app_name: str, ui_urls: Sequence[str]):
        super().__init__('/templates/index.xsl')
        self._app_name = app_name
        self._ui_urls = ui_urls

    def _handle(self, request):
        index_page_data = {
            "app_name": self._app_name,
            "ui_urls": [ui_url for ui_url in self._ui_urls],
            }
        self._send_template_data(request, index_page_data)


class _BatchesFTRedirect(MethodHandler):
    _path = '/batches-ft/'
    _method = HTTPMethod.GET

    def _handle(self, request):
        request.send_response(HTTPStatus.FOUND.value)
        request.send_header('Location', _ListWorkers.url(('group', 'ft:tasks_batch_run')))
        request.end_headers()


class _InvalidQuery(Exception):
    pass


_logger = logging.getLogger(__name__)
