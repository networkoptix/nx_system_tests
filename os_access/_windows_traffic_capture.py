# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from subprocess import CalledProcessError

from os_access._path import RemotePath
from os_access._traffic_capture import TrafficCapture
from os_access._winrm_shell import WinRMShell


class WindowsTrafficCapture(TrafficCapture):

    def __init__(self, dir: RemotePath, winrm_shell: WinRMShell):
        super(WindowsTrafficCapture, self).__init__(dir)
        self._winrm_shell = winrm_shell

    def _stop_orphans(self):
        try:
            self._winrm_shell.run(
                [
                    'taskkill',
                    '/f',  # forcefully terminate the process(es)
                    # Commented out for behaviour be exactly the same as under posix:
                    # '/t',  # terminates the specified process and any child processes which were started by it
                    '/im',  # specifies the image name of the process to be terminated
                    'nmcap.exe',
                    ],
                timeout_sec=120,
                )
        except CalledProcessError as e:
            # https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/taskkill
            # No return values are described in the manual, but 0x80 is raised when there is no tasks to kill
            if e.returncode != 0x80:
                raise

    def _start_capturing_command(self, capture_path, size_limit_bytes, duration_limit_sec):
        return self._winrm_shell.Popen([
            'NMCap',
            '/CaptureProcesses', '/RecordFilters', '/RecordConfig',
            '/DisableLocalOnly',  # P-mode (promiscuous) to capture ICMP.
            '/Capture',  # `/Capture` is an action.
            # Here may come filter in Network Monitor language.
            '/Networks', '*',  # All network interfaces.
            '/File', '{}:{}'.format(capture_path, size_limit_bytes),  # File path and size limit.
            '/StopWhen', '/TimeAfter', duration_limit_sec, 'seconds',
            ])
