# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time
from abc import ABCMeta
from abc import abstractmethod

from infrastructure._message import MessageInput

_logger = logging.getLogger(__name__)


class UpdateService:

    def __init__(self, update_input: MessageInput, update_output_factory: 'UpdateReportFactory'):
        self._update_input = update_input
        self._update_output_factory = update_output_factory

    def process_one_update(self):
        retry_interval_sec = 5
        retry_count = 12
        message_raw = self._update_input.read_message()
        if message_raw is None:
            return
        for attempt in range(1, retry_count + 1):
            _logger.debug("Report attempt %s/%s: %s", attempt, retry_count, message_raw)
            try:
                self._update_output_factory.send_report(message_raw)
                break
            except TemporaryReportError as e:
                _logger.info("Failure %s/%s: %s: %s", attempt, retry_count, e, message_raw)
            except PermanentReportError as e:
                _logger.info("Permanent failure: %s: %s", e, message_raw)
                break
            time.sleep(retry_interval_sec)
        self._update_input.acknowledge()  # Not acknowledged on unhandled exceptions.


class UpdateReportFactory(metaclass=ABCMeta):

    @abstractmethod
    def send_report(self, message_raw):
        pass


class TemporaryReportError(Exception):
    pass


class PermanentReportError(Exception):
    pass
