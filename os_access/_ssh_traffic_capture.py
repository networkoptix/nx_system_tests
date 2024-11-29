# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from subprocess import CalledProcessError

from os_access._path import RemotePath
from os_access._ssh_shell import Ssh
from os_access._traffic_capture import TrafficCapture


class SSHTrafficCapture(TrafficCapture):

    def __init__(self, shell: Ssh, dir: RemotePath):
        super(SSHTrafficCapture, self).__init__(dir)
        self._shell = shell

    def _stop_orphans(self):
        try:
            self._shell.run(['killall', '-SIGKILL', 'tshark'])
        except CalledProcessError as e:
            if e.returncode != 1:
                raise

    def _start_capturing_command(self, capture_path, size_limit_bytes, duration_limit_sec):
        return self._shell.Popen(
            [
                'tshark',
                '-b', 'filesize:{:d}'.format(size_limit_bytes // 1024),
                '-a', 'duration:{:d}'.format(duration_limit_sec),
                '-w', capture_path,
                '-n',  # Disable network object name resolution
                '-i', 'any',  # Capture on all interfaces
                ],
            terminal=True,
            )
