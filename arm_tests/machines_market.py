# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import getpass
import hashlib
import logging
import platform
import subprocess
import time
from abc import ABCMeta
from abc import abstractmethod
from contextlib import AbstractContextManager
from contextlib import closing
from typing import Any
from typing import Mapping

from arm_tests.machine_description import MachineDescription
from os_access import PosixAccess


class RunningMachine(AbstractContextManager, metaclass=ABCMeta):

    @abstractmethod
    def monitor(self, timeout: float):
        pass

    @abstractmethod
    def get_os_access(self) -> PosixAccess:
        pass

    @abstractmethod
    def unlock(self):
        pass

    @abstractmethod
    def commit(self):
        pass


class MachinesMarket(metaclass=ABCMeta):

    @abstractmethod
    def lease(self, description: Mapping[str, Any]) -> RunningMachine:
        pass


class _Snapshot(metaclass=ABCMeta):

    @abstractmethod
    def lease(self, market: MachinesMarket) -> RunningMachine:
        pass


class RootSnapshot(_Snapshot):

    def __init__(self, description: MachineDescription):
        self._description = description

    def lease(self, market: MachinesMarket) -> RunningMachine:
        return market.lease(self._description.make_request(_get_uniq_identifier()))


class _PrerequisitesSnapshot(_Snapshot):

    def __init__(self, description: MachineDescription, prerequisites_name: str):
        self._description = description
        self._prerequisites_name = prerequisites_name

    def lease(self, market: MachinesMarket) -> RunningMachine:
        _body, version = self._description.get_versioned_prerequisites(self._prerequisites_name)
        request = self._description.make_request(version, _get_uniq_identifier())
        return market.lease(request)

    def prepare(self, market: MachinesMarket):
        body, version = self._description.get_versioned_prerequisites(self._prerequisites_name)
        request = self._description.make_request(version)
        with market.lease(request) as running_machine:
            try:
                with closing(running_machine.get_os_access()) as posix_access:
                    _run_temporary_script(posix_access, body)
            except Exception as e:
                _logger.exception("An exception occurred. Rollback requested", exc_info=e)
                running_machine.unlock()
                raise
            running_machine.commit()


def _run_temporary_script(posix_access: PosixAccess, script_body: bytes):
    tmp_script_name = hashlib.sha1(script_body).hexdigest() + '.sh'
    tmp_script = posix_access.home() / tmp_script_name
    _logger.info("Execute script %s", tmp_script)
    tmp_script.write_bytes(script_body)
    tmp_script.chmod(0o744)
    execution_timeout = 180
    try:
        posix_access.shell.run([str(tmp_script.absolute())], timeout_sec=execution_timeout)
    except subprocess.CalledProcessError as err:
        _logger.warning(err.stdout)
        _logger.error(err.stderr)
        raise
    tmp_script.unlink()


class MediaserverPrerequisitesSnapshot(_PrerequisitesSnapshot):

    def __init__(self, description: MachineDescription):
        super().__init__(description, prerequisites_name='mediaserver')


class ClientPrerequisitesSnapshot(_PrerequisitesSnapshot):

    def __init__(self, description: MachineDescription):
        super().__init__(description, prerequisites_name='client')


class _ComponentSnapshot(_Snapshot):

    def __init__(self, description: MachineDescription, identifier: str, name: str):
        self._description = description
        self._identifier = identifier
        self._name = name

    def lease(self, market: MachinesMarket) -> RunningMachine:
        _body, prerequisites_version = self._description.get_versioned_prerequisites(self._name)
        disk_stems = [prerequisites_version, self._identifier, _get_uniq_identifier()]
        return market.lease(self._description.make_request(*disk_stems))

    def open(self, market: MachinesMarket) -> RunningMachine:
        _body, prerequisites_version = self._description.get_versioned_prerequisites(self._name)
        disk_stems = [prerequisites_version, self._identifier]
        return market.lease(self._description.make_request(*disk_stems))


def _get_uniq_identifier() -> str:
    # It must be taken into account that a temporary machine may be requested by
    # multiple clients running in different hosts
    return f"{platform.node()}_{getpass.getuser()}_{time.monotonic()}"


class MediaserverSnapshot(_ComponentSnapshot):

    def __init__(self, description: MachineDescription, distrib_url: str):
        distrib_id = hashlib.sha1(distrib_url.encode()).hexdigest()
        super().__init__(description, distrib_id, name='mediaserver')


class ClientSnapshot(_ComponentSnapshot):

    def __init__(self, description: MachineDescription, distrib_url: str):
        distrib_id = hashlib.sha1(distrib_url.encode()).hexdigest()
        super().__init__(description, distrib_id, name='client')


_logger = logging.getLogger(__name__)
