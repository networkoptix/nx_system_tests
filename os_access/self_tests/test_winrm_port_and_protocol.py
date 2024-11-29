# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import socket
import struct
import time
import urllib.request
from contextlib import closing
from http.client import HTTPResponse
from pprint import pformat

from os_access.self_tests._windows_vm import windows_vm_running

_logger = logging.getLogger(__name__)


def test_port_open(exit_stack):
    """Port is open even if OS is still booting."""
    windows_vm = exit_stack.enter_context(windows_vm_running())
    hostname = '127.0.0.1'
    port = windows_vm.os_access.get_port('tcp', windows_vm.os_access.WINRM_PORT)
    client = socket.socket()
    # Forcefully reset connection when closed.
    # Otherwise, there are FIN-ACK and ACK from other connection before normal handshake in Wireshark.
    # See: https://stackoverflow.com/a/6440364/1833960
    l_onoff = 1
    l_linger = 0
    client.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', l_onoff, l_linger))
    started_at = time.monotonic()
    with closing(client):
        while True:
            try:
                client.connect((hostname, port))
                break
            except TimeoutError:
                pass
            if time.monotonic() - started_at > 300:
                raise AssertionError("Can't connect to %s:%d")
            _logger.info("Couldn't connect to %s:%d; sleep", hostname, port)
            time.sleep(5)


def test_http_is_understood(exit_stack):
    windows_vm = exit_stack.enter_context(windows_vm_running())
    hostname = '127.0.0.1'
    port = windows_vm.os_access.get_port('tcp', windows_vm.os_access.WINRM_PORT)
    url = 'http://{}:{}/wsman'.format(hostname, port)
    started_at = time.monotonic()
    while True:
        try:
            response: HTTPResponse = urllib.request.urlopen(url, timeout=10)
        except urllib.request.HTTPError as err:
            error_content = err.read()
            _logger.info("HTTP ERROR response: %s\n%s", err, error_content)
            break
        except ConnectionError:
            if time.monotonic() - started_at > 600:
                raise AssertionError()
            _logger.info("HTTP response is not received; sleep", hostname, port)
            time.sleep(5)
            continue
        content = response.read()
        _logger.debug(
            "Response:\n%d\n%s\n%r", response, pformat(response.headers), content)
        break
