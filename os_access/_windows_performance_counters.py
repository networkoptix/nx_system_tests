# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from typing import Collection
from typing import Mapping
from typing import Optional

from os_access._winrm import WinRM


class PerformanceCounterEngine:

    def __init__(self, winrm: WinRM):
        self._winrm = winrm

    def request_unfiltered(self, counter_name: str) -> Collection[Mapping[str, Optional[str]]]:
        return [value for _selector, value in self._winrm.wsman_all(counter_name)]

    def request_filtered(
            self,
            counter_name: str,
            selectors: Mapping[str, str],
            ) -> Collection[Mapping[str, Optional[str]]]:
        return [value for _selector, value in self._winrm.wsman_select(counter_name, selectors)]


_logger = logging.getLogger(__name__)
