# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import ipaddress
import json
import logging
import pathlib
import threading
from contextlib import contextmanager
from functools import partial
from http.server import BaseHTTPRequestHandler
from http.server import HTTPServer
from http.server import SimpleHTTPRequestHandler
from pathlib import Path
from typing import Collection

import requests

from ca import default_ca

_logger = logging.getLogger(__name__)


class _BaseServingHTTPServer(HTTPServer):

    def __init__(self, server_address, handler_class):
        super().__init__(server_address, handler_class)
        self._thread = None

    def __enter__(self):
        self._thread = threading.Thread(
            target=self.serve_forever,
            daemon=True,
            )
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._thread is None:
            raise RuntimeError("Not running")
        self.shutdown()
        self._thread.join(timeout=10)
        self._thread = None
        self.server_close()  # Only close prevents from re-start.


class _ProxyPageHandler(SimpleHTTPRequestHandler):

    def __init__(self, *args, external_image_address, **kwargs):
        self._external_image_path = external_image_address
        super().__init__(*args, **kwargs)

    def do_GET(self):
        _logger.info("Request from %s", self.client_address)
        directory = pathlib.Path(self.directory)
        if self.path == '/':
            with open(directory / 'index.html') as index_file:
                data = index_file.read()
            if self._external_image_path:
                updated_data = data.format(server_base_url=self._external_image_path)
            else:
                _logger.info(
                    "No external image address is provided."
                    "Serve local image instead of external resource")
                updated_data = data.format(server_base_url='/local.svg')
            encoded = updated_data.encode()
            content_length = len(encoded)
            self.send_response(200)
            self.send_header('Content-length', str(content_length))
            self.end_headers()
            self.wfile.write(encoded)
        elif self.path == '/local.svg':
            encoded = open(directory / 'local.svg', 'rb').read()
            self.send_response(200)
            self.send_header('Content-type', 'image/svg+xml')
            self.end_headers()
            self.wfile.write(encoded)
        else:
            _logger.info("Unknown path %s is requested", self.path)

    def log_message(self, format, *args):
        _logger.info(format, *args)


class _ImageHandler(SimpleHTTPRequestHandler):

    def do_GET(self):
        if self.path == "/check_proxy_image.svg":
            current_path = Path(__file__).parent
            with open(current_path / 'proxy_web_page' / 'check_proxy_image.svg') as f:
                data = f.read()
            encoded = data.encode()
            content_length = len(encoded)
            self.send_response(200)
            self.send_header('Content-length', str(content_length))
            self.send_header('Content-type', 'image/svg+xml')
            self.end_headers()
            self.wfile.write(encoded)

    def log_message(self, format, *args):
        _logger.info(format, *args)


class _ServeImageHTTPServer(_BaseServingHTTPServer):

    def __init__(self, ip_addresses_to_check_proxy: Collection[str] = ('0.0.0.0', )):
        super().__init__(('', 0), _ImageHandler)
        self._addresses_to_check_proxy = [ipaddress.ip_address(ip) for ip in ip_addresses_to_check_proxy]

    def verify_request(self, request, client_address) -> bool:
        address, _ = client_address
        return ipaddress.ip_address(address) in self._addresses_to_check_proxy

    def log_message(self, format, *args):
        _logger.info(format, *args)


class _Handler(BaseHTTPRequestHandler):

    def __init__(self, *args, data, simple_data, stored_headers, **kwargs):
        self._data = data
        self._simple_data = simple_data
        self._stored_headers = stored_headers
        super().__init__(*args, **kwargs)

    def _load_post_data(self):
        content_length = int(self.headers.get('content-length', 0))
        post_data = self.rfile.read(content_length)
        try:
            return json.loads(post_data.decode())
        except json.JSONDecodeError:
            return post_data.decode()

    def _post_is_ok(self):
        self.send_response(200)
        self.send_header('Content-length', '0')
        self.end_headers()

    def do_GET(self):
        if self.path == "/show_last_post_content":
            if self._data:
                decoded_data = json.dumps(self._data)
                encoded = decoded_data.encode()
            elif self._simple_data:
                data = self._simple_data[-1]
                encoded = bytes(data, 'utf-8')
            else:
                raise RuntimeError("No data received")
            self.send_response(200)
            for head in self._stored_headers.items():
                self.send_header(*head)
            self.end_headers()
            self.wfile.write(encoded)
        if self.path == "/show_headers":
            self.send_response(200)
            headers_length = len(bytes(self.headers))
            self.send_header('Content-length', str(headers_length))
            self.end_headers()
            _logger.info('%r: Headers are: %s', self, self.headers)
            self.wfile.write(bytes(self.headers))

    def do_POST(self):
        if self.path == "/receive":
            data = self._load_post_data()
            self._stored_headers.update(self.headers)
            _logger.info("Received %s", data)
            if isinstance(data, dict):
                self._data.update(data)
            else:
                self._simple_data.append(data)
            self._post_is_ok()

    def log_message(self, format, *args):
        _logger.info(format, *args)


class TestRequestHTTPServer(_BaseServingHTTPServer):

    def __init__(self):
        self._data = {}
        self._simple_data = []
        self._stored_headers = {}
        self._handler = partial(
            _Handler,
            data=self._data,
            simple_data=self._simple_data,
            stored_headers=self._stored_headers,
            )
        super().__init__(('0.0.0.0', 0), self._handler)
        self.port = self.server_port

    def retrieve_latest_post_content(self):
        [address, port] = self.server_address
        response = requests.get(
            f"http://{address}:{port}/show_last_post_content")
        _logger.info("Received text %s", response.text)
        return response


def create_test_http_server(dir_with_index_file):
    index_file_path = str(Path(__file__).parent / dir_with_index_file)
    return _BaseServingHTTPServer(
        server_address=('', 0),
        handler_class=partial(SimpleHTTPRequestHandler, directory=index_file_path))


@contextmanager
def create_proxy_image_server(
        *,
        ip_addresses_to_check_proxy: Collection[str],
        source_address_from_client: str,
        ):
    hostnames = [source_address_from_client, '127.0.0.1']
    image_server = _ServeImageHTTPServer(ip_addresses_to_check_proxy)
    image_server.socket = default_ca().wrap_server_socket(image_server.socket, hostnames)
    with image_server:
        directory = str(Path(__file__).parent / 'proxy_web_page')
        image_link = f"https://{source_address_from_client}:{image_server.server_port}/check_proxy_image.svg"
        serving_https_server = _BaseServingHTTPServer(
            server_address=('', 0),
            handler_class=partial(
                _ProxyPageHandler,
                directory=directory,
                external_image_address=image_link))
        serving_https_server.socket = default_ca().wrap_server_socket(serving_https_server.socket, hostnames)
        with serving_https_server:
            yield serving_https_server
