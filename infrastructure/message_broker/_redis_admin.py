# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import netrc
from abc import ABCMeta
from abc import abstractmethod
from functools import lru_cache
from pathlib import Path

from redis import Redis

from infrastructure._provisioning import get_user_choice


def run_with_confirmation(command: '_RedisAdminCommand'):
    print(f"Following commands will be executed:\n{command.explain()}\n\n")
    confirmation = get_user_choice("Confirm", ['yes', 'no'])
    if confirmation == 'no':
        print("Abort")
        return
    command.run()


class _RedisAdminCommand(metaclass=ABCMeta):

    def __init__(self):
        self._redis = _redis_admin()

    @abstractmethod
    def run(self):
        pass

    @abstractmethod
    def explain(self) -> str:
        pass


class DeleteStream(_RedisAdminCommand):

    def __init__(self, stream: str):
        super().__init__()
        self._stream = stream
        self._delete_group_commands = [
            DeleteGroup(stream, g['name'])
            for g in self._redis.xinfo_groups(stream)
            ]

    def __repr__(self):
        return f"{self.__class__.__name__}(stream={self._stream!r})"

    def explain(self):
        return '\n'.join(c.explain() for c in self._delete_group_commands) + '\n' + repr(self)

    def run(self):
        for command in self._delete_group_commands:
            command.run()
        _logger.info("Run %r", self)
        self._redis.delete(self._stream)


class DeleteGroup(_RedisAdminCommand):

    def __init__(self, stream: str, group: str):
        super().__init__()
        self._stream = stream
        self._group = group
        self._delete_consumer_commands = [
            DeleteConsumer(stream, group, c['name'])
            for c in self._redis.xinfo_consumers(stream, group)
            ]

    def __repr__(self):
        return f"{self.__class__.__name__}(stream={self._stream!r}, group={self._group!r})"

    def explain(self):
        return '\n'.join(c.explain() for c in self._delete_consumer_commands) + '\n' + repr(self)

    def run(self):
        for command in self._delete_consumer_commands:
            command.run()
        _logger.info("Run %r", self)
        self._redis.xgroup_destroy(self._stream, self._group)


class DeleteConsumer(_RedisAdminCommand):

    def __init__(self, stream: str, group: str, consumer: str):
        super().__init__()
        self._stream = stream
        self._group = group
        self._consumer = consumer

    def __repr__(self):
        return (
            f"{self.__class__.__name__}("
            f"stream={self._stream!r}, "
            f"group={self._group!r}, "
            f"consumer={self._consumer!r})")

    def explain(self):
        return repr(self)

    def run(self):
        _logger.info("Run %r", self)
        self._redis.xgroup_delconsumer(self._stream, self._group, self._consumer)


@lru_cache(1)
def _redis_admin() -> Redis:
    host = 'sc-ft003.nxlocal'
    netrc_store = netrc.netrc(Path('~/.config/.secrets/redis.netrc').expanduser())
    [username, _, password] = netrc_store.authenticators(host)
    return Redis(host=host, username=username, password=password, decode_responses=True)


_logger = logging.getLogger(__name__)
