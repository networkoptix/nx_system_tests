# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import os

if os.name == 'nt':
    from .local_windows_shell import local_windows_shell  # noqa: F401
    local_shell = local_windows_shell
else:
    from .local_posix_shell import local_posix_shell  # noqa: F401
    local_shell = local_posix_shell
