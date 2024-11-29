# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import email.utils
import html
import io
import logging
import os
import re
import sys
import urllib
import urllib.parse
from contextlib import contextmanager
from datetime import datetime
from datetime import timezone
from http import HTTPStatus
from http.server import HTTPServer
from http.server import SimpleHTTPRequestHandler
from pathlib import Path
from threading import Thread
from typing import BinaryIO
from typing import Generator

from directories import get_run_dir


def _read_chunked(fd: BinaryIO) -> Generator[bytes, None, None]:
    while True:
        chunk_size = int(fd.readline().strip(), base=16)
        data = fd.read(chunk_size)
        end = fd.read(2)
        if end != b'\r\n':
            raise RuntimeError(f"Incorrect chunk end flag {end} instead of '\\r\\n'")
        if chunk_size == 0:
            break
        yield data


_logger = logging.getLogger("SERVER")


class _HTTPHandler(SimpleHTTPRequestHandler):

    directory: str

    def _get_local_server_dir(self) -> Path:
        return Path(self.directory).absolute()

    def _get_request_path(self) -> Path:
        return Path(self.translate_path(self.path)).absolute()

    def list_directory(self, path):
        # HTTP servers like NGINX return not only directory list but a link to a parent dir as well
        # This handler is a complete copy of SimpleHTTPRequestHandler.list_directory()
        # except adding of the '../' url and format changes making the handler more readable.
        try:
            list = os.listdir(path)
        except OSError:
            self.send_error(
                HTTPStatus.NOT_FOUND,
                "No permission to list directory")
            return None
        list.sort(key=lambda a: a.lower())
        r = []
        try:
            displaypath = urllib.parse.unquote(self.path, errors='surrogatepass')
        except UnicodeDecodeError:
            displaypath = urllib.parse.unquote(path)
        displaypath = html.escape(displaypath, quote=False)
        enc = sys.getfilesystemencoding()
        title = 'Directory listing for %s' % displaypath
        r.append('<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd">')
        r.append('<html>\n<head>')
        r.append('<meta http-equiv="Content-Type" content="text/html; charset=%s">' % enc)
        r.append('<title>%s</title>\n</head>' % title)
        r.append('<body>\n<h1>%s</h1>' % title)
        r.append('<hr>\n<ul>')
        # Add parent link
        parent_link = urllib.parse.urljoin(self.path, '../..')
        parent_link_encoded = urllib.parse.quote(parent_link, errors='surrogatepass')
        parent_name_encoded = html.escape('../../', quote=False)
        r.append('<li><a href="%s">%s</a></li>' % (parent_link_encoded, parent_name_encoded))

        for name in list:
            fullname = os.path.join(path, name)
            displayname = linkname = name
            # Append / for directories or @ for symbolic links
            if os.path.isdir(fullname):
                displayname = name + "/"
                linkname = name + "/"
            if os.path.islink(fullname):
                displayname = name + "@"
                # Note: a link to a directory displays with @ and links with /
            link_encoded = urllib.parse.quote(linkname, errors='surrogatepass')
            name_encoded = html.escape(displayname, quote=False)
            r.append('<li><a href="%s">%s</a></li>' % (link_encoded, name_encoded))
        r.append('</ul>\n<hr>\n</body>\n</html>\n')
        encoded = '\n'.join(r).encode(enc, 'surrogateescape')
        f = io.BytesIO()
        f.write(encoded)
        f.seek(0)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-type", "text/html; charset=%s" % enc)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        return f

    def _get_stream_offset(self) -> int:
        range_header = self.headers.get('Range')
        if range_header is None:
            return 0
        match = re.match(r"^bytes=(\d+)-.*$", range_header)
        return int(match.groups()[0])

    def do_PUT(self):
        request_file = self._get_request_path()
        _logger.info("Received PUT request to %s", request_file)
        with request_file.open('wb') as target_fd:
            for chunk in _read_chunked(self.rfile):
                target_fd.write(chunk)
        self.send_response(HTTPStatus.CREATED)
        self.end_headers()

    def do_DELETE(self):
        request_file = self._get_request_path()
        _logger.info("Received DELETE request to %s", request_file)
        request_file.unlink(missing_ok=True)
        self.send_response(HTTPStatus.OK)
        self.end_headers()

    def send_head(self):
        # Python HTTP server does not support Range header which implies changes in the
        # Content-Length header as well. This handler is a complete copy of
        # SimpleHTTPRequestHandler.send_head() except setting a correct Content-Length header
        # and fixing code style errors.
        path = self.translate_path(self.path)
        f = None
        if os.path.isdir(path):
            parts = urllib.parse.urlsplit(self.path)
            if not parts.path.endswith('/'):
                # redirect browser - doing basically what apache does
                self.send_response(HTTPStatus.MOVED_PERMANENTLY)
                new_parts = (parts[0], parts[1], parts[2] + '/', parts[3], parts[4])
                new_url = urllib.parse.urlunsplit(new_parts)
                self.send_header("Location", new_url)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return None
            for index in "index.html", "index.htm":
                index = os.path.join(path, index)
                if os.path.isfile(index):
                    path = index
                    break
            else:
                return self.list_directory(path)
        ctype = self.guess_type(path)
        # check for trailing "/" which should return 404. See Issue17324
        # The test for this was added in test_httpserver.py
        # However, some OS platforms accept a trailingSlash as a filename
        # See discussion on python-dev and Issue34711 regarding
        # parseing and rejection of filenames with a trailing slash
        if path.endswith("/"):
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return None
        try:
            f = open(path, 'rb')
        except OSError:
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return None
        try:
            fs = os.fstat(f.fileno())
            # Use browser cache if possible
            if "If-Modified-Since" in self.headers and "If-None-Match" not in self.headers:
                # compare If-Modified-Since and time of last file modification
                try:
                    ims = email.utils.parsedate_to_datetime(
                        self.headers["If-Modified-Since"])
                except (TypeError, IndexError, OverflowError, ValueError):
                    # ignore ill-formed values
                    pass
                else:
                    if ims.tzinfo is None:
                        # obsolete format with no timezone, cf.
                        # https://tools.ietf.org/html/rfc7231#section-7.1.1.1
                        ims = ims.replace(tzinfo=timezone.utc)
                    if ims.tzinfo is timezone.utc:
                        # compare to UTC datetime of last modification
                        last_modif = datetime.fromtimestamp(
                            fs.st_mtime, timezone.utc)
                        # remove microseconds, like in If-Modified-Since
                        last_modif = last_modif.replace(microsecond=0)

                        if last_modif <= ims:
                            self.send_response(HTTPStatus.NOT_MODIFIED)
                            self.end_headers()
                            f.close()
                            return None
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-type", ctype)
            offset = self._get_stream_offset()
            if offset > 0:
                _logger.info("Requested offset: %s", offset)
                f.seek(offset)
            self.send_header("Content-Length", str(fs[6] - offset))
            # noinspection PyTypeChecker
            # See: https://youtrack.jetbrains.com/issue/PY-66518/http.server.BaseHTTPRequestHandler.datetimestring-narrow-type-hint
            self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
            self.end_headers()
            return f
        except Exception:
            f.close()
            raise

    def log_message(self, format, *args):
        _logger.debug(format, *args)


@contextmanager
def http_server_serving():
    tmp_path = get_run_dir()
    server = HTTPServer(
        ("127.0.0.1", 0),
        lambda *args: _HTTPHandler(*args, directory=str(tmp_path)))
    _logger.info("Run HTTP server at %s:%s for %s", *server.server_address, tmp_path)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        thread.join()
        # HTTPServer does not wait its socket closure
        # what may lead to AddressAlreadyInUse error at the next test
        server.socket.close()
