# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from subprocess import CalledProcessError
from subprocess import TimeoutExpired

from os_access import PosixAccess
from os_access import RemotePath
from os_access import WindowsAccess


class WindowsDebugger:

    def __init__(self, os_access: WindowsAccess):
        self._os_access = os_access
        self._windows_kits_directory = r'C:\Program Files (x86)\Windows Kits'
        # See: https://networkoptix.atlassian.net/wiki/spaces/SD/pages/3469180933/MS+Symbols+Server
        self._symbol_servers = (
            'srv*https://artifactory.us.nxteam.dev/artifactory/ms-symbols;'
            'srv*https://artifactory.us.nxteam.dev/artifactory/ms-symbols-raw'
            )

    def save_backtrace(self, pid: int, backtrace_file: RemotePath):
        self._disable_certificate_revocation_check()
        # See: https://learn.microsoft.com/en-us/windows-hardware/drivers/debuggercmds/debugger-commands
        command = [
            self.find_cdb(),
            '-pv',  # Noninvasive mode.
            '-p', str(pid),
            '-y', self._symbol_servers,
            '-c', (  # Execute commands:
                '.lines -e;'  # source line support,
                '!analyze -v;'  # information about the current exception (extension),
                '.exr -1;'  # last exception,
                '.ecxr;'  # last exception context,
                'kP;'  # stack trace, with all parameters of all functions,
                '~*kP;'  # all threads backtrace, with all parameters of all functions,
                'q'),  # quit.
            ]
        try:
            result = self._os_access.run(
                command,
                timeout_sec=600,  # It takes a while when symbols are not cached yet.
                )
        except CalledProcessError:
            # Sometimes CDB can't attach to the process, and it finished with an error like this:
            #       WARNING: Process 1234 is not attached as a debuggee
            #       The process can be examined but debug events will not be received
            _logger.exception("There seems to be an issue with collecting a backtrace")
        except TimeoutExpired:
            # Collection of a backtrace for a long-running test can be time-consuming.
            _logger.exception("Collecting a backtrace takes too much time")
        else:
            backtrace_file.write_bytes(result.stdout)

    def parse_core_dump(self, dump_file: RemotePath) -> bytes:
        self._disable_certificate_revocation_check()
        # See: https://learn.microsoft.com/en-us/windows-hardware/drivers/debuggercmds/debugger-commands
        result = self._os_access.run(
            command=[
                self.find_cdb(),
                '-z',
                dump_file,
                # `-y` is string with a special format. Example: `cache*;srv*;\\server\share\symbols\product\v100500`.
                # See: https://docs.microsoft.com/en-us/windows-hardware/drivers/debugger/symbol-path
                '-y', self._symbol_servers,
                '-c', (  # execute commands:
                    '.lines -e;'  # source line support,
                    '!analyze -v;'  # information about the current exception (extension),
                    '.exr -1;'  # last exception,
                    '.ecxr;'  # last exception context,
                    'kP;'  # stack trace, with all parameters of all functions,
                    '~*kP;'  # all threads backtrace, with all parameters of all functions,
                    'q'),  # quit.
                ],
            timeout_sec=600,  # It takes a while when symbols are not cached yet.
            )
        # Return bytes because the output is going to be written into a file.
        return result.stdout

    def find_cdb(self) -> RemotePath:
        try:
            kits = [*self._os_access.path(self._windows_kits_directory).iterdir()]
        except FileNotFoundError:
            raise DebuggerNotFound(
                f"Windows Kits directory is missing {self._windows_kits_directory}",
                )
        if not kits:
            raise DebuggerNotFound(f"Empty directory {self._windows_kits_directory}")
        try:
            [kit] = kits
        except ValueError:
            raise RuntimeError("Too many subdirectories in windows kits directory.")
        path = kit / r'Debuggers\x64\cdb.exe'
        if not path.exists():
            raise DebuggerNotFound(f"No such file or directory {path}")
        return path

    def _disable_certificate_revocation_check(self):
        # Disable the certificate revocation check; otherwise, it doesn't work with
        # https://artifactory.us.nxteam.dev.
        self._os_access.registry.set_dword(
            r'HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Internet Settings',
            'CertificateRevocation', 0,
            )


class PosixDebugger:

    def __init__(self, os_access: PosixAccess, gdb_path: RemotePath, lib_dir: RemotePath):
        self._os_access = os_access
        self._gdb_path = gdb_path
        self._lib_dir = lib_dir

    def save_backtrace(self, pid: int, backtrace_file: RemotePath):
        # Temporarily stopping the process to avoid gdb attach hang.
        try:
            with self._os_access.process_paused(pid):
                self._os_access.shell.run(
                    [
                        self._gdb_path,
                        '--quiet',
                        '--eval-command', 'set verbose on',
                        '--eval-command', 'set logging off',  # It is needed for the command below to work.
                        '--eval-command', 'set logging overwrite off',  # Append.
                        '--eval-command', 'set logging redirect off',
                        '--eval-command', f'set logging file {backtrace_file}',
                        '--eval-command', 'set logging on',
                        '--eval-command', f'attach {pid}',
                        '--eval-command', 'set print static-members off',
                        '--eval-command', 'thread apply all backtrace',
                        '--eval-command', 'quit',
                        ],
                    env={'LD_LIBRARY_PATH': self._lib_dir},
                    timeout_sec=90,
                    )
        except CalledProcessError:
            # VMs with Linux have 1 Gb RAM, and it might not be enough to take a backtrace.
            _logger.exception("There seems to be an issue with collecting a backtrace")
        except TimeoutExpired:
            # Collection of a backtrace for a long-running test can be time-consuming.
            _logger.exception("Collecting a backtrace takes too much time")

    def parse_core_dump(self, executable: RemotePath, dump_file: RemotePath) -> bytes:
        command = [
            self._gdb_path,
            '--quiet',
            '--core',
            dump_file,
            '--exec',
            executable,
            '--eval-command', 'set print static-members off',
            '--eval-command', 'thread apply all backtrace',
            '--eval-command', 'quit',
            ]
        outcome = self._os_access.shell.run(
            command,
            env={'LD_LIBRARY_PATH': self._lib_dir},
            timeout_sec=600,
            )
        return outcome.stdout


class DebuggerNotFound(Exception):
    pass


_logger = logging.getLogger(__name__)
