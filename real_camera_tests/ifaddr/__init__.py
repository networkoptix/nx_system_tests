# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import platform
from ipaddress import IPv4Interface
from typing import Mapping
from typing import Sequence

__all__ = ['get_local_ipv4_interfaces']


_platform = platform.system()


if _platform == "Linux":
    from .linux import get_local_ipv4_interfaces
elif _platform == "Windows":
    from .windows import get_local_ipv4_interfaces
else:
    def get_local_ipv4_interfaces() -> Mapping[str, Sequence[IPv4Interface]]:
        raise RuntimeError(
            f"There is no implementation of {__all__[0]}() for platform {_platform}")
