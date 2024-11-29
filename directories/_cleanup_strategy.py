# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from abc import ABCMeta
from abc import abstractmethod

from directories._directories import EntryRoot


class CleanupStrategy(metaclass=ABCMeta):

    def __init__(self, target_size: int, last_cleanup_at: float, entry_root: EntryRoot):
        self._target_size = target_size
        self._last_cleanup_at = last_cleanup_at
        self._entry_root = entry_root

    @abstractmethod
    def delete_least_significant(self):
        pass


_logger = logging.getLogger(__name__)
