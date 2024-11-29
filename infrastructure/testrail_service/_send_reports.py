# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
import logging
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs

from infrastructure._http import HTTPMethod
from infrastructure._http import MethodHandler
from infrastructure.testrail_service._testrail_api import TestrailApi


class PostTestsMappingResult(MethodHandler):
    _path = '/send_results'
    _method = HTTPMethod.POST

    def __init__(self, testrail_api: TestrailApi):
        self._testrail_api = testrail_api

    def _handle(self, request: BaseHTTPRequestHandler):
        payload = _parse_form(_get_form(request))
        request.send_response(HTTPStatus.OK)
        request.send_header('Content-Type', 'text/plain; charset=utf-8')
        request.end_headers()
        _logger.debug("Make %d requests", len(payload))
        for sent, [uri, data] in enumerate(payload, start=1):
            request.wfile.write(f"POST {uri} {len(data)} bytes ({sent}/{len(payload)}) ".encode())
            started_at = time.monotonic()
            self._testrail_api.post(uri, data)
            time_spent = time.monotonic() - started_at
            request.wfile.write(f"OK ({time_spent:.1f} sec)\n".encode())
        request.wfile.write("DONE".encode())


def _get_form(request):
    content_length = int(request.headers['Content-Length'])
    content = request.rfile.read(content_length).decode()
    _logger.debug("_PostTestsMappingResult form: %s", content[:1024])
    return parse_qs(content)


def _parse_form(form):
    requests = json.loads(form['requests'][0])
    return [
        (raw['uri'], json.dumps(raw['data']).encode())
        for raw in requests
        ]


_logger = logging.getLogger(__name__)
