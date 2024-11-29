# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import functools
import logging
import time

from os_access._exceptions import ServiceAlreadyStopped
from os_access._exceptions import ServiceNotFoundError
from os_access._exceptions import ServiceRecoveredAfterStop
from os_access._exceptions import ServiceStatusError
from os_access._exceptions import ServiceUnstoppableError
from os_access._service_interface import Service
from os_access._service_interface import ServiceStartError
from os_access._service_interface import ServiceStatus
from os_access._winrm import WinRM
from os_access._winrm import WinRMOperationTimeoutError
from os_access._winrm import WmiError
from os_access._winrm import WmiInvokeFailed
from os_access._winrm import WmiObjectNotFound


class _WindowsService(Service):

    def __init__(self, winrm: WinRM, name: str):
        self._winrm = winrm
        self._name = name

    def __repr__(self):
        return '<_WindowsService {} at {}>'.format(self._name, self._winrm)

    @functools.lru_cache()
    def get_username(self):
        return "LocalSystem"

    _errors = {
        0: "The request was accepted.",
        1: "The request is not supported.",
        2: "The user did not have the necessary access.",
        3: "The service cannot be stopped because other services that are running are dependent on it.",
        4: "The requested control code is not valid, or it is unacceptable to the service.",
        5: "The requested control code cannot be sent to the service because the state of the service (Win32_BaseService.State property) is equal to 0, 1, or 2.",
        6: "The service has not been started.",
        7: "The service did not respond to the start request in a timely fashion.",
        8: "Unknown failure when starting the service.",
        9: "The directory path to the service executable file was not found.",
        10: "The service is already running.",
        11: "The database to add a new service is locked.",
        12: "A dependency this service relies on has been removed from the system.",
        13: "The service failed to find the service needed from a dependent service.",
        14: "The service has been disabled from the system.",
        15: "The service does not have the correct authentication to run on the system.",
        16: "This service is being removed from the system.",
        17: "The service has no execution thread.",
        18: "The service has circular dependencies when it starts.",
        19: "A service is running under the same name.",
        20: "The service name has invalid characters.",
        21: "Invalid parameters have been passed to the service.",
        22: "The account under which this service runs is either invalid or lacks the permissions to run the service.",
        23: "The service exists in the database of services available from the system.",
        24: "The service is currently paused in the system.",
        }

    def _wait_until_stop(self, pid_before_stop, timeout_sec: float):
        _logger.debug("Wait until %s stops.", self)
        started_at = time.monotonic()
        while True:
            instance = self._winrm.wsman_get('Win32_Service', {'Name': self._name})
            state = instance['State']
            status = instance['Status']
            if state == 'Stopped' and status == 'OK':
                break
            pid = instance['ProcessId']
            if pid != pid_before_stop:
                raise ServiceRecoveredAfterStop(
                    f"{self._name} changed its PID from {pid_before_stop} to {pid}")
            time_left = timeout_sec - (time.monotonic() - started_at)
            _logger.debug(
                "%s Status: %s; state: %s; seconds left %s",
                self, status, state, time_left)
            if time.monotonic() - started_at > timeout_sec:
                raise ServiceUnstoppableError(f"{self} didn't stop after {timeout_sec} seconds.")
            time.sleep(4)

    def stop(self, timeout_sec=None):
        if timeout_sec is None:
            timeout_sec = 30
        service_info = self._winrm.wsman_get('Win32_Service', {'Name': self._name})
        pid_before = service_info['ProcessId']
        try:
            self._winrm.wsman_invoke('Win32_Service', {'Name': self._name}, 'StopService', {})
        # https://docs.microsoft.com/en-us/windows/desktop/cimwin32prov/stopservice-method-in-class-win32-service
        except WmiInvokeFailed as e:
            if e.return_value == 7:
                # The service may have stopped even if the stop command timed out.
                _logger.warning(
                    "Timed out by OS: %s. Check if service is already stopped.", self._name)
                self._wait_until_stop(pid_before, timeout_sec=timeout_sec)
            elif e.return_value == 8:
                _logger.error(
                    "Error stopping %s; a crash may be the cause; "
                    "SCM will restart it, unless many crashes happened before; "
                    "wait a while to see what SCM will do.",
                    self._name)
                # What happens if SCM restarts it (State / Status):
                # - Stopped / OK for 0.1 sec,
                # - Start Pending / Degraded for 0.7 sec,
                # - Running / OK.
                # Otherwise, service remains Stopped / OK.
                time.sleep(1)
                instance = self._winrm.wsman_get('Win32_Service', {'Name': self._name})
                if instance['State'] != 'Stopped':
                    if instance['State'] not in {'Start Pending', 'Running'}:
                        raise RuntimeError(self._name + " in an unexpected state")
                    _logger.error(
                        "Give %s a few seconds to initialize properly. "
                        "The initial problem VMS-14306 was that assertion failure "
                        "happened if it's stopped 2 seconds after a restart.",
                        self._name)
                    time.sleep(4)  # TODO: Check repeatedly for something specific.
                    try:
                        self._winrm.wsman_invoke('Win32_Service', {'Name': self._name}, 'StopService', {})
                    except WmiInvokeFailed as ee:
                        if ee.return_value == 7:
                            raise ServiceUnstoppableError(
                                "Timed out after error 8 recovery: " + self._name)
                        else:
                            raise
                    _logger.error("OK: %s stopped properly.", self._name)
            elif e.return_value == 5:
                raise ServiceAlreadyStopped(f"{self._name} is already stopped.")
            else:
                default_message = f"Unknown error {e.return_value}"
                message = self._errors.get(e.return_value, default_message)
                raise RuntimeError(f"Cannot stop {self._name}: {message}")
        except WinRMOperationTimeoutError:
            raise ServiceUnstoppableError("WinRM operation timed out: " + self._name)
        except WmiError as e:
            if e.code != WmiError.NOT_FOUND:
                raise
            raise ServiceNotFoundError("%s not found: " + self._name)
        else:
            self._wait_until_stop(pid_before, timeout_sec=timeout_sec)

    def start(self, timeout_sec=None):
        started_at = time.monotonic()
        try:
            self._winrm.wsman_invoke(
                'Win32_Service', {'Name': self._name}, 'StartService', {},
                timeout_sec=timeout_sec)
        except WmiInvokeFailed as e:
            default_message = f"Unknown error {e.return_value}"
            message = self._errors.get(e.return_value, default_message)
            raise ServiceStartError(f"Cannot start {self._name}: {message}")
        while True:
            instance = self._winrm.wsman_get('Win32_Service', {'Name': self._name})
            instance_state = instance['State']
            if instance_state == 'Running':
                _logger.debug("Service {} has been started".format(self))
                return
            elif instance_state == 'Start Pending':
                _logger.debug("Service {} start pending".format(self))
            else:
                raise ServiceStartError("Invalid state: {}".format(instance_state))
            if timeout_sec is not None:
                if time.monotonic() > started_at + timeout_sec:
                    raise ServiceStartError(
                        "Timed out waiting for service to start: {}".format(self))
            time.sleep(0.5)

    def status(self):
        try:
            instance = self._winrm.wsman_get('Win32_Service', {'Name': self._name})
        except WmiObjectNotFound:
            raise ServiceNotFoundError(f"Service {self._name!r} not found")
        # See: https://learn.microsoft.com/en-us/windows/win32/cimwin32prov/win32-service
        if instance['State'].endswith('Pending'):
            return ServiceStatus(False, False, 0)
        if instance['Status'] not in {'OK', 'Degraded'}:
            return ServiceStatus(False, False, 0)
        if instance['ProcessId'] == '0':
            if instance['Started'] != 'false' or instance['State'] != 'Stopped':
                raise ServiceStatusError(f"Service status inconsistent: {instance}")
            return ServiceStatus(False, True, 0)
        else:
            if instance['Started'] != 'true' or instance['State'] != 'Running':
                raise ServiceStatusError(f"Service status inconsistent: {instance}")
            return ServiceStatus(True, False, int(instance['ProcessId']))

    def create(self, command):
        raise NotImplementedError("Difficult to create a service on Windows")


_logger = logging.getLogger(__name__)
