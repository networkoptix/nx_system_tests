# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from __future__ import annotations

import json
import logging
from functools import partial
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Mapping
from urllib.parse import parse_qs
from urllib.parse import unquote
from urllib.parse import urlparse

from infrastructure._http import App
from infrastructure._http import HTTPMethod
from infrastructure._http import MethodHandler
from infrastructure._http import StaticFilesHandler
from infrastructure._http import XSLTemplateHandler
from infrastructure.build_registry.builds_database import BuildsDatabase
from infrastructure.build_registry.builds_database import InvalidMetadataQuery


def make_app(builds_database: BuildsDatabase):
    app_root_path = Path(__file__).parent
    return partial(App, handlers=[
        StaticFilesHandler(app_root_path, relative_paths=[
            '/templates/builds_records_table.css',
            '/templates/builds_records_table.xsl',
            ]),
        _GetBuildRecordsTable(builds_database),
        _GetBuildRecordsMetadata(builds_database),
        _AddBuildRecords(builds_database),
        ])


class _GetBuildRecordsTable(XSLTemplateHandler):
    _path = '/'
    _method = HTTPMethod.GET

    def __init__(self, builds_db: BuildsDatabase):
        self._builds_db = builds_db
        super().__init__('/templates/builds_records_table.xsl')

    def _handle(self, request: BaseHTTPRequestHandler):
        query = urlparse(request.path).query
        if query:
            try:
                metadata = _parse_query(query)
            except _InvalidQuery as err:
                request.send_error(HTTPStatus.BAD_REQUEST, str(err))
                return
            try:
                metadata_records = self._builds_db.full_text_search(metadata=metadata)
            except InvalidMetadataQuery as err:
                request.send_error(HTTPStatus.BAD_REQUEST, str(err))
                return
        else:
            metadata_records = self._builds_db.list_recent()
        data = []
        for raw_metadata in metadata_records:
            metadata = dict(line.split('=', 1) for line in raw_metadata.splitlines() if line)
            if 'ft:url' not in metadata:
                continue
            data.append({
                'url': metadata['ft:url'],
                'root_disk_url': metadata.get('ft:root_disk_url', ''),
                # Decode the URL-encoded mediaserver disk URL,
                # to allow searching in the table where this data is displayed.
                'mediaserver_disk_url': unquote(metadata.get('ft:mediaserver_disk_url', '')),
                })
        self._send_template_data(request, data)


class _GetBuildRecordsMetadata(MethodHandler):
    _path = '/builds'
    _method = HTTPMethod.GET

    def __init__(self, builds_db: BuildsDatabase):
        self._builds_db = builds_db

    def _handle(self, request: BaseHTTPRequestHandler):
        query = urlparse(request.path).query
        if query:
            try:
                metadata = _parse_query(query)
            except _InvalidQuery as err:
                request.send_error(HTTPStatus.BAD_REQUEST, str(err))
                return
            try:
                metadata_records = self._builds_db.full_text_search(metadata=metadata)
            except InvalidMetadataQuery as err:
                request.send_error(HTTPStatus.BAD_REQUEST, str(err))
                return
        else:
            metadata_records = self._builds_db.list_recent()
        request.send_response(HTTPStatus.OK)
        request.send_header('Content-Type', 'application/json')
        request.end_headers()
        logging.info("Received metadata %s", metadata_records)
        request.wfile.write(json.dumps(metadata_records, indent=2).encode('utf-8'))


class _AddBuildRecords(MethodHandler):
    _path = '/builds'
    _method = HTTPMethod.POST

    def __init__(self, builds_db: BuildsDatabase):
        self._builds_db = builds_db

    def _handle(self, request: BaseHTTPRequestHandler):
        length = int(request.headers.get('content-length'))
        post_data = request.rfile.read(length)
        self._builds_db.add_build(post_data.decode('utf-8'))
        request.send_response(HTTPStatus.OK)
        request.end_headers()


class _InvalidQuery(Exception):
    pass


def _parse_query(query: str) -> Mapping[str, str]:
    params = parse_qs(query, strict_parsing=True)
    if not params:
        raise _InvalidQuery("No query parameters provided")
    metadata = {}
    for key, value in params.items():
        if len(value) > 1:
            raise _InvalidQuery(f"Duplicated {key} parameter")
        metadata[key] = value[0]
    return metadata
