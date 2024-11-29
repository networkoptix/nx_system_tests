# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from doubles.licensing._licensing_server import LicenseServer
from doubles.licensing._remote_licensing_server import ValidationError
from doubles.licensing._remote_licensing_server import get_remote_licensing_server

__all__ = [
    'LicenseServer',
    'ValidationError',
    'get_remote_licensing_server',
    ]
