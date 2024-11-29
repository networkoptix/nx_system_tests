# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import socket
from contextlib import AbstractContextManager
from contextlib import contextmanager
from datetime import datetime
from datetime import timezone
from typing import Mapping
from typing import Optional

from installation import Mediaserver
from mediaserver_api import EventState
from mediaserver_api import EventType
from mediaserver_api import MediaserverApi
from mediaserver_api import RuleAction
from tests.single_server.event_rules.http_server import HttpServer


@contextmanager
def recording_camera(mediaserver: Mediaserver, sample_media_file):
    [camera] = mediaserver.add_cameras_with_archive(
        sample_media_file=sample_media_file,
        start_times=[datetime(2019, 1, 1, tzinfo=timezone.utc)])
    with mediaserver.api.camera_recording(camera.id):
        yield camera


@contextmanager
def http_server() -> AbstractContextManager[HttpServer]:
    r"""HTTP server that synchronous catches requests synchronously.

    >>> with http_server() as server:
    ...     with socket.create_connection(('127.0.0.1', server.port)) as sock:
    ...         request_text = (
    ...             'POST /sample_uri HTTP/1.0\r\n'
    ...             'Sample_Key: Sample_Value\r\n'
    ...             'Content-Length: 10\r\n'
    ...             '\r\n'
    ...             '0123456789')
    ...         sock.sendall(request_text.encode('ascii'))
    ...         with server.wait() as request:
    ...             assert request.method == 'POST'
    ...             assert request._uri == '/sample_uri'
    ...             assert request.header('Sample_Key') == 'Sample_Value'
    ...             assert request.text == '0123456789'
    ...             request.respond('201 Created')
    ...         [response_data, _] = sock.recv(1000).split(b'\r\n', 1)
    ...         assert response_data == 'HTTP/1.0 201 Created'.encode('ascii')

    """
    with socket.create_server(('0.0.0.0', 0)) as sock:
        yield HttpServer(sock)


@contextmanager
def event(
        api: MediaserverApi,
        action: RuleAction,
        params: Optional[Mapping] = None,
        ) -> AbstractContextManager:
    rule_id = api.add_event_rule(
        event_type=EventType.USER_DEFINED,
        event_state=EventState.UNDEFINED,
        action=action,
        )
    params = {} if params is None else params
    api.create_event(
        source=params.get('source', ''),
        caption=params.get('caption', 'irrelevant'),
        description=params.get('description', ''))
    yield
    api.remove_event_rule(rule_id)


def url_for(port: int, hostname: str, uri: str, auth: Optional[str] = None) -> str:
    scheme = 'http'  # making https is hard - we need to generate certificates
    auth = f'{auth}@' if auth is not None else ''
    return f'{scheme}://{auth}{hostname}:{port}{uri}'


def expected(template: str, params: Mapping) -> str:
    billet = template.replace("{event.source}", params.get('source', ''))
    billet = billet.replace("{event.caption}", params.get('caption', 'irrelevant'))
    return billet.replace("{event.description}", params.get('description', ''))
