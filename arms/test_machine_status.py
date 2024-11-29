# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import asyncio
import logging
import socket
import tempfile
import unittest
from contextlib import aclosing
from contextlib import closing
from pathlib import Path

from arms.machine_status import UnixSocketStatusEndpoint


class TestUnixMachineStatus(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self._tmp_dir = Path(tempfile.mkdtemp())
        _logger.info("TMP dir is %s", self._tmp_dir)

    async def test_success(self):
        socket_path = self._tmp_dir / 'arbitrary.sock'
        async with aclosing(UnixSocketStatusEndpoint(socket_path)) as status_endpoint:  # type: UnixSocketStatusEndpoint
            status_before = await _retrieve_all_data(str(socket_path))
            self.assertIn("Status: IDLE", status_before)
            self.assertIn("Successes: 0", status_before)
            self.assertIn("Failures: 0", status_before)
            with status_endpoint.serving():
                status_serving = await _retrieve_all_data(str(socket_path))
                self.assertIn("Status: RUNNING", status_serving)
                self.assertIn("Successes: 0", status_serving)
                self.assertIn("Failures: 0", status_serving)
            status_after = await _retrieve_all_data(str(socket_path))
            self.assertIn("Status: IDLE", status_after)
            self.assertIn("Successes: 1", status_after)
            self.assertIn("Failures: 0", status_after)

    async def test_failure(self):

        class _ArbitraryException(Exception):
            pass

        socket_path = self._tmp_dir / 'arbitrary.sock'
        async with aclosing(UnixSocketStatusEndpoint(socket_path)) as status_endpoint:  # type: UnixSocketStatusEndpoint
            status_before = await _retrieve_all_data(str(socket_path))
            self.assertIn("Status: IDLE", status_before)
            self.assertIn("Successes: 0", status_before)
            self.assertIn("Failures: 0", status_before)
            with self.assertRaises(_ArbitraryException):
                with status_endpoint.serving():
                    raise _ArbitraryException()
            status_after = await _retrieve_all_data(str(socket_path))
            self.assertIn("Status: IDLE", status_after)
            self.assertIn("Successes: 0", status_after)
            self.assertIn("Failures: 1", status_after)

    async def test_multiple_outcomes(self):

        class _ArbitraryException(Exception):
            pass

        socket_path = self._tmp_dir / 'arbitrary.sock'
        async with aclosing(UnixSocketStatusEndpoint(socket_path)) as status_endpoint:  # type: UnixSocketStatusEndpoint
            status_before = await _retrieve_all_data(str(socket_path))
            self.assertIn("Successes: 0", status_before)
            self.assertIn("Failures: 0", status_before)
            with self.assertRaises(_ArbitraryException):
                with status_endpoint.serving():
                    raise _ArbitraryException()
            with status_endpoint.serving():
                pass
            with self.assertRaises(_ArbitraryException):
                with status_endpoint.serving():
                    raise _ArbitraryException()
            with status_endpoint.serving():
                pass
            with self.assertRaises(_ArbitraryException):
                with status_endpoint.serving():
                    raise _ArbitraryException()
            status_after = await _retrieve_all_data(str(socket_path))
            self.assertIn("Successes: 2", status_after)
            self.assertIn("Failures: 3", status_after)


async def _retrieve_all_data(unix_socket_path: str) -> str:
    with closing(await _connected_unix_socket(unix_socket_path)) as client_socket:
        reader, writer = await asyncio.open_unix_connection(sock=client_socket)
        try:
            return (await reader.read()).decode()
        finally:
            writer.close()
            await writer.wait_closed()


async def _connected_unix_socket(raw_path: str) -> socket.socket:
    client_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client_socket.setblocking(False)
    connect_coroutine = asyncio.get_running_loop().sock_connect(client_socket, raw_path)
    try:
        await asyncio.wait_for(connect_coroutine, timeout=1)
    except Exception:
        client_socket.close()
        raise
    return client_socket


_logger = logging.getLogger(__name__)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)7s %(name)s %(message).5000s",
        )
    unittest.main()
