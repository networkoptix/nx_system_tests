# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from abc import ABCMeta
from abc import abstractmethod
from typing import Optional
from typing import Sequence


class MessageBatchInput(metaclass=ABCMeta):

    @abstractmethod
    def list_latest_messages(self) -> Sequence[str]:
        pass

    @abstractmethod
    def id(self) -> str:
        pass


class MessageInput(metaclass=ABCMeta):

    @abstractmethod
    def read_message(self) -> Optional[str]:
        pass

    @abstractmethod
    def acknowledge(self):
        pass

    @abstractmethod
    def id(self) -> str:
        pass


class MessageOutput(metaclass=ABCMeta):

    @abstractmethod
    def write_message(self, message: str):
        pass

    @abstractmethod
    def is_alive(self) -> bool:
        pass

    @abstractmethod
    def id(self) -> str:
        pass
