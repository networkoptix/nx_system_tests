# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import errno


class UnknownExitStatus(Exception):

    def __init__(self, stdout, stderr):
        self.stdout = stdout
        self.stderr = stderr


class NotEmpty(OSError):

    def __init__(self, code, message):
        if code is None:
            code = errno.ENOTEMPTY
        super(NotEmpty, self).__init__(code, message)


class CannotDelete(OSError):
    pass


class ServiceUnstoppableError(Exception):
    pass


class ServiceNotFoundError(Exception):
    pass


class ServiceAlreadyStopped(Exception):
    pass


class DeviceBusyError(Exception):
    pass


class ServiceRecoveredAfterStop(Exception):
    pass


class ServiceFailedDuringStop(Exception):
    pass


class ProcessStopError(Exception):
    pass


class ServiceStatusError(Exception):
    pass
