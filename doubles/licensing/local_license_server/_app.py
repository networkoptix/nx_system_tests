# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
import logging
from typing import Any
from typing import Collection
from typing import Mapping
from typing import Sequence
from typing import Union
from urllib.parse import parse_qs
from urllib.parse import urlparse

from doubles.licensing.local_license_server._license import activate_license
from doubles.licensing.local_license_server._license import deactivate_license
from doubles.licensing.local_license_server._license import generate_license
from doubles.licensing.local_license_server._license import validate_license


def app(environ, start_response):
    try:
        return _app(environ, start_response)
    except Exception:
        _logger.exception("Exception in local license server app:")
        raise


def _app(environ, start_response):
    _logger.debug("New request, environ %s", environ)
    try:
        response_body = _process_request(environ)
    except _RespondWithError as e:
        response_status = e.response_status
        response_body = e.response_body
    else:
        response_status = '200 OK'
    _logger.debug(
        "Response to %s: %s %s", environ['REMOTE_ADDR'], response_status, response_body)
    start_response(response_status, [])
    return response_body


def _process_request(environ) -> Sequence[bytes]:
    method = environ['REQUEST_METHOD']
    remote_address = environ['REMOTE_ADDR']
    request_path = urlparse(environ['PATH_INFO']).path.rstrip('/')
    if method == 'POST':
        data = _get_data(environ)
        _logger.debug("POST request from %s, path %s data %s", remote_address, request_path, data)
        return _process_post_request(request_path, data)
    if method == 'GET':
        _logger.debug("GET request from %s, path %s", remote_address, request_path)
        query = environ['QUERY_STRING']
        if query:
            parsed_query = _parse_query(query)
        else:
            parsed_query = {}
        return _process_get_request(request_path, parsed_query)
    raise _RespondWithError('405 Method Not Allowed')


def _process_post_request(request_path: str, data: Mapping[Any, Any]) -> Sequence[bytes]:
    if request_path == '/nxlicensed/checklogin.php':
        return [b'']
    if request_path == '/nxlicensed/genkey.php':
        return _generate_license_response(data)
    if request_path in ['/nxlicensed/activation', '/nxlicensed/activate.php']:
        return _activate_license_response(
            data['license_key'],
            data['version'],
            {k: v for k, v in data.items() if k.startswith('hwid')},
            )
    if request_path == '/nxlicensed/api/v1/deactivate':
        for license_record in data['licenses']:
            deactivate_license(license_record['key'])
        return [b'']
    if request_path == '/nxlicensed/api/v1/validate':
        return _validate_license_response(
            data['info']['version'], [vms_license['key'] for vms_license in data['licenses']])
    raise _RespondWithError('404 Not Found')


def _generate_license_response(data) -> Sequence[bytes]:
    [key, serial] = generate_license(data)
    items = {'items': [{'key': key, 'serial': serial}]}
    return [json.dumps(items).encode('ascii')]


def _process_get_request(request_path: str, query: Mapping[str, Any]) -> Sequence[bytes]:
    if request_path == '/nxlicensed/checklogin.php':
        return [b'']
    if request_path.startswith('/nxlicensed/api/v2/license/inspect/'):
        # This path is not in license server sources. Response with empty dict works.
        return [b'{}']
    if request_path == '/nxlicensed/api/v2/license/cloud/licenses':
        # Implementation for cloud systems is not done yet.
        return [b'']
    raise _RespondWithError('404 Not Found')


def _activate_license_response(
        key: str,
        vms_version: str,
        hwids: Mapping[str, Union[str, Collection[str]]],
        ) -> Sequence[bytes]:
    activation = activate_license(key, vms_version, hwids)
    return [activation.encode('ascii')]


def _validate_license_response(vms_version: str, keys: Collection[str]):
    result = validate_license(vms_version, keys)
    return [json.dumps(result).encode('ascii')]


def _get_data(environ):
    content_length = environ.get('CONTENT_LENGTH') or '0'
    raw_content = environ['wsgi.input'].read(int(content_length))
    if not raw_content:
        return {}
    content = raw_content.decode('ascii')
    content_type = environ['CONTENT_TYPE']
    if content_type == 'application/json':
        return json.loads(content)
    if content_type == 'application/x-www-form-urlencoded':
        # If field specified multiple times - only last value will be saved.
        # Such parsing is wrong in general case but will work here.
        return _parse_query(content)
    raise _RespondWithError(
        '400 Bad Request',
        response_body=[b'Unsupported content type ', content_type.encode('ascii')])


def _parse_query(query) -> Mapping[str, Any]:
    result = {}
    parsed = parse_qs(query)
    for key, values in parsed.items():
        try:
            [value] = values
        except ValueError:
            result[key] = values
        else:
            result[key] = value
    return result


class _RespondWithError(Exception):

    def __init__(self, response_status: str, response_body: Sequence[bytes] = ()):
        super().__init__(response_status)
        self.response_status = response_status
        self.response_body = response_body


_logger = logging.getLogger(__name__)
