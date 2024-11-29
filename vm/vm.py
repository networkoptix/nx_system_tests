# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time
from datetime import datetime
from datetime import timezone
from pathlib import Path

from os_access import OsAccess
from os_access import OsAccessNotReady
from vm.hypervisor import Vm


class VM:

    def __init__(self, vm_control: Vm, os_access: OsAccess):
        self.vm_control = vm_control
        self.os_access = os_access

    def ensure_started(self, artifacts_dir: Path):
        # Ubuntu 20 and 22 sometimes get stuck at boot with
        # last lines in console:
        # "Freeing unused kernel image (initmem) memory:"
        #
        # It is a long-lasting problem since 2.6 kernels popping up
        # in different environments for kernels 2.6 - 5.19
        # which origins have not been tracked yet.
        #
        # See: https://www.virtualbox.org/ticket/12069
        # See: https://www.linuxquestions.org/questions/linux-software-2/hang-after-freeing-unused-kernel-memory-211275/
        # See: https://unix.stackexchange.com/questions/685254/debian-stalls-at-boot-freeing-unused-kernel-image-initmem-memory-2656k
        max_attempts = 4
        attempt = 0
        started_at = time.monotonic()
        while True:
            attempt += 1
            try:
                self.os_access.wait_ready(timeout_sec=90)
            except OsAccessNotReady:
                self._take_screenshot(artifacts_dir)
                if attempt > max_attempts:
                    raise
                self._reset()
                continue
            _logger.info(
                "%r: started in %.1f seconds, following %d attempts",
                self, time.monotonic() - started_at, attempt)
            return

    def _take_screenshot(self, directory: Path):
        date_suffix = datetime.now(tz=timezone.utc).strftime("%Y%m%d%H%M%S")
        prefix = self.os_access.netloc().replace(':', '-')
        screenshot_file = directory / f'{prefix}_{date_suffix}.png'
        self.vm_control.take_screenshot(screenshot_file)

    def _reset(self):
        self.os_access.close()
        self.vm_control.reset()
        _logger.info("%r: Sleep while definitely rebooting...", self)
        time.sleep(3)

    def __repr__(self):
        return f"<VM {self.vm_control!r}:{self.os_access!r}>"


_logger = logging.getLogger(__name__)
