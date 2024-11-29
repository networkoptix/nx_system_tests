# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import os
from datetime import datetime
from datetime import timezone
from functools import lru_cache


@lru_cache()
def create_time():
    """Creation time of this process, same as OS utilities report.

    The creation time is visible within the process and from the OS.
    It can be used as a nearly unique id to track a run, its run dir,
    Jenkins job and various logs.
    """
    if os.name == 'nt':
        from ctypes import WinError, byref, windll
        from ctypes.wintypes import HANDLE
        from ctypes.wintypes import FILETIME
        result = FILETIME()
        success = windll.kernel32.GetProcessTimes(
            HANDLE(windll.kernel32.GetCurrentProcess()),
            byref(result),
            byref(FILETIME()),
            byref(FILETIME()),
            byref(FILETIME()),
            )
        if not success:
            raise WinError()
        # FILETIME contains a 64-bit value representing
        # the number of 100-nanosecond intervals since January 1, 1601 (UTC).
        # noinspection PyTypeChecker
        result = result.dwHighDateTime << 32 | result.dwLowDateTime
        result -= 116444736000000000
        result /= 1e7
    else:
        # On Linux, process creation time is relative to boot time.
        # Therefore, the result may be inaccurate.
        # But the same algorithm is used in the ps utility.
        with open('/proc/stat') as f:
            [boot_time] = (line for line in f if line.startswith('btime '))
        [_, boot_time] = boot_time.split()
        boot_time = int(boot_time)
        with open('/proc/self/stat') as f:
            result = f.read().split()[21]
        result = int(result)
        result /= 100
        result += boot_time
    return datetime.fromtimestamp(result, timezone.utc)
