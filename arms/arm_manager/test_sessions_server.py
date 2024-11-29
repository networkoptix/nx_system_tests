# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import asyncio
import logging
import unittest

from arms.arm_manager.server import SessionsServer
from arms.arm_manager.server import _ConcurrentSession
from arms.arm_manager.server import bind_server_socket


class TestSessionsServer(unittest.IsolatedAsyncioTestCase):

    class _EchoSession(_ConcurrentSession):

        def __init__(
                self,
                reader: asyncio.StreamReader,
                writer: asyncio.StreamWriter,
                logger: logging.Logger,
                ):
            super().__init__(reader, writer)
            self._logger = logger

        def status(self):
            pass

        async def _serve(self):
            self._logger.info("%s: Serving", self)
            while result := await self._reader.read(1):
                logging.info("%s: Received %r", self, result)
                self._writer.write(result)
                await asyncio.sleep(0)
            self._logger.info("%s: Connection closed", self)

        def close(self):
            self._logger.info("%s: Close request received", self)
            self._writer.close()

        async def wait_closed(self):
            self._logger.info("%s: Waiting for writer to close ...", self)
            await asyncio.gather(self._task, self._writer.wait_closed())
            self._logger.info("%s: Closed", self)

        def __repr__(self):
            return f'<EchoSession: {self._peername}>'

    async def test_stop_server_having_two_sessions(self):
        server_socket = bind_server_socket("127.0.0.50", 0)
        server_host, server_port = server_socket.getsockname()
        logger = logging.getLogger('client_logger')
        with self.assertLogs(logger, 'INFO') as gathered:
            async with SessionsServer[self._EchoSession](server_socket) as server:
                server_coroutine = server.serve(lambda r, w: self._EchoSession(r, w, logger))
                serve_task = asyncio.create_task(server_coroutine)
                await asyncio.sleep(0)
                reader_one, writer_one = await asyncio.open_connection(server_host, server_port)
                reader_two, writer_two = await asyncio.open_connection(server_host, server_port)
                data_to_send_one = b'IRRELEVANT DATA FIRST'
                data_to_send_two = b'IRRELEVANT DATA SECOND'
                writer_one.write(data_to_send_one)
                writer_two.write(data_to_send_two)
                logging.info("Sent %r to first stream", data_to_send_one)
                logging.info("Sent %r to second stream", data_to_send_two)
                received_data_one = await reader_one.readexactly(len(data_to_send_one))
                received_data_two = await reader_two.readexactly(len(data_to_send_two))
                self.assertEqual(data_to_send_one, received_data_one)
                self.assertEqual(data_to_send_two, received_data_two)
                server.stop()
                await serve_task
        joined_logs = '|'.join(gathered.output)
        logging.info("Joined logs: %s", joined_logs)
        self.assertIn('Close request received', joined_logs)
        self.assertIn('Closed', joined_logs)


class TestSessionsServerStopserverTimeout(unittest.IsolatedAsyncioTestCase):

    class _EchoSession(_ConcurrentSession):

        def status(self):
            pass

        async def _serve(self):
            logging.info("%s: Serving", self)
            while result := await self._reader.read(1):
                logging.info("%s: Received %r", self, result)
                self._writer.write(result)
                await asyncio.sleep(0)
            logging.info("%s: Connection closed", self)

        def close(self):
            logging.info("%s: Close request received", self)
            self._writer.close()

        async def wait_closed(self):
            logging.info("%s: Emulate stuck session ...", self)
            await asyncio.sleep(60)
            logging.info("%s: Closed", self)

        def __repr__(self):
            return f'<EchoSession: {self._peername}>'

    async def test_stop_server_timeout(self):
        server_socket = bind_server_socket("127.0.0.50", 0)
        server_host, server_port = server_socket.getsockname()
        server = await SessionsServer[self._EchoSession](server_socket).__aenter__()
        serve_task = asyncio.create_task(server.serve(lambda r, w: self._EchoSession(r, w)))
        await asyncio.sleep(0)
        _, _ = await asyncio.open_connection(server_host, server_port)
        server.stop()
        await serve_task
        with self.assertRaises(asyncio.TimeoutError):
            await server.__aexit__(None, None, None)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)7s %(name)s %(message).5000s",
        )
    unittest.main()
