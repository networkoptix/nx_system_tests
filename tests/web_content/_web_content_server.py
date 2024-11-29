# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import mimetypes
import os
import ssl
import threading
import wsgiref.simple_server
from contextlib import contextmanager
from pathlib import Path
from typing import Collection
from typing import Optional

from ca import default_ca
from distrib import Distrib


@contextmanager
def static_web_content_artifactory_url(static_web_content, runner_address, distrib: Distrib):
    app = _StaticWebContentArtifactory(static_web_content.path)
    hostnames = ['127.0.0.1', runner_address]
    if distrib.newer_than('vms_5.0'):
        cert_file_path = _make_certificate(hostnames)
    else:
        cert_file_path = None
    wsgi_server = _WsgiServer(app, cert_file_path=cert_file_path)
    with wsgi_server.serving():
        yield f'https://{runner_address}:{wsgi_server.port}/{static_web_content.path.name}'


class _StaticWebContentArtifactory:

    def __init__(self, archive_path: Path):
        self._file_path = archive_path
        self._file_size = self._file_path.stat().st_size

    def __call__(self, _, start_response):
        [content_type, _] = mimetypes.guess_type(self._file_path)
        start_response('200 OK', [
            ('Content-Length', f'{self._file_size}'),
            ('Content-Type', content_type),
            ])
        yield from self._read_data()

    def _read_data(self):
        chunk_size_bytes = 1024**2
        with open(self._file_path, 'rb') as fp:
            current_pos = 0
            fp.seek(current_pos)
            while True:
                next_chunk_size = min(self._file_size - current_pos + 1, chunk_size_bytes)
                if next_chunk_size == 0:
                    break
                data = fp.read(next_chunk_size)
                current_pos += next_chunk_size
                yield data


def _make_certificate(hostnames: Collection[str]) -> Path:
    certificates_dir = Path('~/.cache').expanduser()
    certificates_dir.mkdir(parents=False, exist_ok=True)
    key_and_cert_path = certificates_dir / 'static_web_content_artifactory_key_and_cert.pem'
    if not key_and_cert_path.exists():
        key_and_cert_data = default_ca().generate_key_and_cert(*hostnames)
        key_and_cert_path.write_text(key_and_cert_data)
    return key_and_cert_path


class _WsgiServer:

    def __init__(self, app, listen_port=0, cert_file_path: Optional[Path] = None):
        self._server = wsgiref.simple_server.make_server(
            '0.0.0.0', listen_port, app, handler_class=_LoggingWSGIRequestHandler)
        if cert_file_path is not None:
            self._wrap_ssl_socket(cert_file_path)
        _, self.port = self._server.server_address

    def _wrap_ssl_socket(self, cert_file: Path):
        ssl_context = ssl.SSLContext(protocol=ssl.PROTOCOL_TLS_SERVER)
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.VerifyMode.CERT_NONE
        ssl_context.load_cert_chain(cert_file, None)
        ssl_context.keylog_filename = os.environ.get('SSLKEYLOGFILE')
        self._server.socket = ssl_context.wrap_socket(self._server.socket, server_side=True)

    @contextmanager
    def serving(self):
        thread = threading.Thread(target=self._server.serve_forever)
        thread.start()
        try:
            yield
        finally:
            self._server.shutdown()
            thread.join()
            self._server.server_close()


class _LoggingWSGIRequestHandler(wsgiref.simple_server.WSGIRequestHandler):

    def log_message(self, format_string, *args):
        format_message = "%s - - [%s] " + format_string
        _logger.debug(format_message, self.address_string(), self.log_date_time_string(), *args)


_logger = logging.getLogger(__name__)
