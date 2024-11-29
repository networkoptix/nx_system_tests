# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time
from abc import ABCMeta
from abc import abstractmethod
from datetime import datetime
from subprocess import TimeoutExpired
from typing import Optional

from os_access._command import Run
from os_access._exceptions import ProcessStopError
from os_access._path import RemotePath

_logger = logging.getLogger(__name__)

DEFAULT_SIZE_LIMIT_BYTES = 2 * 1024 * 1024 * 1024
DEFAULT_DURATION_LIMIT_SEC = 2 * 60 * 60


class TrafficCapture(metaclass=ABCMeta):

    def __init__(self, dir: RemotePath):
        self._dir: RemotePath = dir
        self._run: Optional[Run] = None
        self._remote_capture_file: Optional[RemotePath] = None

    @abstractmethod
    def _stop_orphans(self):
        pass

    @abstractmethod
    def _start_capturing_command(
            self,
            capture_path: RemotePath,
            size_limit_bytes: int,
            duration_limit_sec: int) -> Run:
        pass

    def start(self):
        self._dir.mkdir(exist_ok=True, parents=True)
        self._remote_capture_file = self._dir / '{:%Y%m%d%H%M%S%u}.cap'.format(datetime.utcnow())
        _logger.info('Start capturing traffic to file %s', self._remote_capture_file)
        self._run = self._start_capturing_command(
            self._remote_capture_file, DEFAULT_SIZE_LIMIT_BYTES, DEFAULT_DURATION_LIMIT_SEC)
        time.sleep(1)

    def _stop_running(self):
        time.sleep(1)
        self._run.terminate()
        _logger.info('Stop capturing traffic to file %s', self._remote_capture_file)
        try:
            stdout, stderr = self._run.communicate(timeout_sec=300)  # Time to clean up.
        except TimeoutExpired:
            raise ProcessStopError("Couldn't stop capturing traffic")
        finally:
            _logger.debug("Exit status: %s", self._run.returncode)
        _logger.debug("STDOUT:\n%s", stdout)
        _logger.debug("STDERR:\n%s", stderr)
        self._run.close()
        self._run = None
        self._remote_capture_file = None

    def stop(self):
        if self._run is not None:
            self._stop_running()
        else:
            _logger.info("Traffic capture was not started")
        logging.info("Stop all orphaned traffic captures processes")
        self._stop_orphans()
        return

    def files(self):
        return sorted(self._dir.glob('*.cap'))

    def is_running(self) -> bool:
        return self._run is not None
