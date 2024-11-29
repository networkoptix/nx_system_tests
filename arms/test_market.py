# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import asyncio
import logging
import socket
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from typing import Any
from typing import Mapping

from arms.market import CommandFailed
from arms.market import Contract
from arms.market import ContractRejected
from arms.market import ContractorQuit
from arms.market import Market
from arms.market import SingleDirectoryStorage
from arms.market import UnixSocketMarket


class TestSingleDirStorage(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self._tmp_dir = Path(tempfile.mkdtemp())
        self._opened_sockets = list[socket.socket]()
        _logger.info("TMP dir is %s", self._tmp_dir)

    def tearDown(self):
        # Avoid ResourceWarning warnings at test failures
        for opened_socket in self._opened_sockets:
            opened_socket.close()

    async def test_lifespan(self):
        sockets_storage = SingleDirectoryStorage(self._tmp_dir)
        first_group_name = "first"
        second_group_name = "second"
        first_group_listeners = [sockets_storage.open_new(first_group_name) for _ in range(2)]
        self._opened_sockets.extend(first_group_listeners)
        first_group_listen_paths = [sock.getsockname() for sock in first_group_listeners]
        second_group_listeners = [sockets_storage.open_new(second_group_name) for _ in range(3)]
        self._opened_sockets.extend(second_group_listeners)
        second_group_listen_paths = [sock.getsockname() for sock in second_group_listeners]
        first_group_clients = [
            sock async for sock in sockets_storage.iter_active_by_age(first_group_name)
            ]
        self._opened_sockets.extend(first_group_clients)
        first_group_client_paths = [sock.getpeername() for sock in first_group_clients]
        second_group_clients = [
            sock async for sock in sockets_storage.iter_active_by_age(second_group_name)
            ]
        self._opened_sockets.extend(second_group_clients)
        second_group_client_paths = [sock.getpeername() for sock in second_group_clients]
        self.assertSequenceEqual(first_group_listen_paths, first_group_client_paths)
        self.assertSequenceEqual(second_group_listen_paths, second_group_client_paths)


class TestUnixMarket(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self._tmp_dir = Path(tempfile.mkdtemp())
        _logger.info("TMP dir is %s", self._tmp_dir)

    async def test_place_and_withdraw_contract(self):
        market_storage = SingleDirectoryStorage(self._tmp_dir)
        market = UnixSocketMarket(market_storage, priority=0)
        arbitrary_description = {'name': 'arbitrary_name'}
        try:
            await asyncio.wait_for(market.find_contractor(arbitrary_description), timeout=0.5)
        except TimeoutError:
            _logger.info("Couldn't find any suitable contract")

    async def test_synchronize_contract_contractee_descriptions(self):
        market_storage = SingleDirectoryStorage(self._tmp_dir)
        market = UnixSocketMarket(market_storage, priority=0)
        arbitrary_contract_description = {'condition': 'irrelevant'}
        arbitrary_contractor_info = {'name': 'arbitrary'}

        async def _contractee():
            contract, contractor_info = await market.find_contractor(
                contract_description=arbitrary_contract_description)
            self.assertEqual(contractor_info, arbitrary_contractor_info)
            contract.close()

        async def _contractor():
            contract, description = await _get_first_contract(market)
            self.assertEqual(description, arbitrary_contract_description)
            async with contract.accepted(contractor_info=arbitrary_contractor_info):
                pass

        await asyncio.gather(_contractee(), _contractor())

    async def test_command_success_fulfil_contract(self):
        market_storage = SingleDirectoryStorage(self._tmp_dir)
        market = UnixSocketMarket(market_storage, priority=0)
        arbitrary_command_description = {'command': 'irrelevant'}
        arbitrary_command_result = {'result': 'irrelevant'}

        async def _reliable_contractee():
            contract, _contractor_info = await market.find_contractor(contract_description={})
            with closing(contract):
                result = await contract.execute_sync(arbitrary_command_description)
            self.assertEqual(result, arbitrary_command_result)

        async def _successful_contractor():
            contract, _description = await _get_first_contract(market)
            async with contract.accepted(contractor_info={}) as accepted_contract:
                async for command, command_description in accepted_contract.handle():
                    self.assertEqual(command_description, arbitrary_command_description)
                    await command.report_success(arbitrary_command_result)

        await asyncio.gather(_reliable_contractee(), _successful_contractor())

    async def test_command_failure_fulfil_contract(self):
        market_storage = SingleDirectoryStorage(self._tmp_dir)
        market = UnixSocketMarket(market_storage, priority=0)
        arbitrary_command_description = {'command': 'irrelevant'}
        arbitrary_command_result = {'result': 'irrelevant'}

        async def _reliable_contractee():
            contract, _contractor_info = await market.find_contractor(contract_description={})
            with closing(contract):
                try:
                    await contract.execute_sync(arbitrary_command_description)
                except CommandFailed as err:
                    self.assertEqual(err.result, arbitrary_command_result)

        async def _unsuccessful_contractor():
            contract, _description = await _get_first_contract(market)
            async with contract.accepted(contractor_info={}) as accepted_contract:
                async for command, command_description in accepted_contract.handle():
                    self.assertEqual(command_description, arbitrary_command_description)
                    await command.report_failure(arbitrary_command_result)

        await asyncio.gather(_reliable_contractee(), _unsuccessful_contractor())

    async def test_fulfil_contracts_series(self):
        market_storage = SingleDirectoryStorage(self._tmp_dir)
        market = UnixSocketMarket(market_storage, priority=0)
        arbitrary_command_description = {'command': 'irrelevant'}
        arbitrary_command_result = {'result': 'irrelevant'}

        async def _reliable_contractee():
            contract, _contractor_info = await market.find_contractor(contract_description={})
            with closing(contract):
                result = await contract.execute_sync(arbitrary_command_description)
            self.assertEqual(result, arbitrary_command_result)

        async def _reliable_contractor():
            contract, _description = await _get_first_contract(market)
            async with contract.accepted(contractor_info={}) as accepted_contract:
                async for command, command_description in accepted_contract.handle():
                    self.assertEqual(command_description, arbitrary_command_description)
                    await command.report_success(arbitrary_command_result)

        # Multiple contracts may be served simultaneously
        await asyncio.gather(
            _reliable_contractee(), _reliable_contractee(),
            _reliable_contractor(), _reliable_contractor())
        # Unix socket files cleanup is performed by following contractors
        await asyncio.gather(
            _reliable_contractee(), _reliable_contractee(),
            _reliable_contractor(), _reliable_contractor())

    async def test_contractee_quit(self):
        market_storage = SingleDirectoryStorage(self._tmp_dir)
        market = UnixSocketMarket(market_storage, priority=0)

        async def _unreliable_contractee():
            contract, _contractor_info = await market.find_contractor(contract_description={})
            with closing(contract):
                await asyncio.sleep(0.125)

        async def _reliable_contractor():
            contract, _description = await _get_first_contract(market)
            async with contract.accepted(contractor_info={}) as accepted_contract:
                async for _command, _command_description in accepted_contract.handle():
                    pass

        await asyncio.gather(_unreliable_contractee(), _reliable_contractor())

    async def test_contractor_quit(self):
        market_storage = SingleDirectoryStorage(self._tmp_dir)
        market = UnixSocketMarket(market_storage, priority=0)
        arbitrary_command_description = {'command': 'irrelevant'}

        async def _reliable_contractee():
            contract, _contractor_info = await market.find_contractor(contract_description={})
            with closing(contract):
                with self.assertRaises(ContractorQuit):
                    await contract.execute_sync(arbitrary_command_description)

        async def _unreliable_contractor():
            contract, _description = await _get_first_contract(market)
            async with contract.accepted(contractor_info={}) as accepted_contract:
                async for _command, _command_description in accepted_contract.handle():
                    await asyncio.sleep(0.125)
                    return

        await asyncio.gather(_reliable_contractee(), _unreliable_contractor())

    async def test_contractor_rejected(self):
        market_storage = SingleDirectoryStorage(self._tmp_dir)
        market = UnixSocketMarket(market_storage, priority=0)
        arbitrary_contract_description = {'condition': 'irrelevant'}
        rejection_message = "Arbitrary reason"

        async def _reliable_contractee():
            with self.assertRaisesRegex(ContractRejected, rejection_message):
                await market.find_contractor(arbitrary_contract_description)

        async def _rejecting_contractor():
            contract, _description = await _get_first_contract(market)
            await contract.reject(rejection_message)

        await asyncio.gather(_reliable_contractee(), _rejecting_contractor())

    async def test_contractor_ignores(self):
        market_storage = SingleDirectoryStorage(self._tmp_dir)
        market = UnixSocketMarket(market_storage, priority=0)
        arbitrary_contract_description = {'condition': 'irrelevant'}

        async def _reliable_contractee():
            coro = market.find_contractor(arbitrary_contract_description)
            try:
                await asyncio.wait_for(coro, timeout=1)
            except TimeoutError:
                pass

        async def _ignoring_contractor():
            contract, _description = await _get_first_contract(market)
            contract.ignore()

        await asyncio.gather(_reliable_contractee(), _ignoring_contractor())


async def _get_first_contract(market: Market) -> tuple[Contract, Mapping[str, Any]]:
    async for description, contract in market.iter_pending_contracts():
        return description, contract
    raise RuntimeError("No suitable contracts found")


_logger = logging.getLogger(__name__)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)7s %(name)s %(message).5000s",
        )
    unittest.main()
