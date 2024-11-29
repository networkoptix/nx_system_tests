# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import shlex
from subprocess import SubprocessError

from os_access._winrm_shell import WinRMShell
from os_access.self_tests._windows_vm import windows_vm_running
from tests.infra import assert_raises
from tests.infra import assert_raises_with_message


def test_remote_process_interaction(exit_stack):
    windows_vm = exit_stack.enter_context(windows_vm_running())
    winrm_shell = WinRMShell(windows_vm.os_access.winrm)
    with winrm_shell.Popen(['more']) as run:
        for i in range(3):
            stdin = ('chunk %d\n' % i).encode('ascii')
            run.send(stdin)
            stdout, stderr = run.receive(None)
            assert stdout.replace(b'\r\n', b'\n') == stdin
        run.send(b'', is_last=True)
        _, _ = run.communicate()


def test_run_command(exit_stack):
    windows_vm = exit_stack.enter_context(windows_vm_running())
    winrm_shell = WinRMShell(windows_vm.os_access.winrm)
    with winrm_shell.Popen(['echo', '123']) as run:
        stdout_bytes, stderr_bytes = run.communicate()
        assert run.returncode == 0
        assert stdout_bytes == b'123\r\n'
        assert stderr_bytes == b''


def test_run_command_with_stdin(exit_stack):
    windows_vm = exit_stack.enter_context(windows_vm_running())
    winrm_shell = WinRMShell(windows_vm.os_access.winrm)
    with winrm_shell.Popen(['more']) as run:
        stdout_bytes, stderr_bytes = run.communicate(b'123')
        assert run.returncode == 0
        assert stdout_bytes == b'123\r\n'
        assert stderr_bytes == b''


# It's important to check all cases, not only complex ones.
# When command is executed via WinRM, cmd /c unquoting rules are applied.
# According to cmd /?, there are several conditions on the number of quotes,
# presence of spaces and special symbols, whether the whole command is a file.
def test_command_passing_args_echo_no_arg(exit_stack):
    _test_command_passing(['echo'], 0, exit_stack)


def test_command_passing_args_echo_arg(exit_stack):
    _test_command_passing(['echo', 'hello'], 0, exit_stack)


def test_command_passing_args_echo_arg_with_space(exit_stack):
    _test_command_passing(['echo', 'hello world'], 0, exit_stack)


def test_command_passing_args_whoami_no_arg(exit_stack):
    _test_command_passing(['whoami'], 0, exit_stack)


def test_command_passing_args_whoami_full_path_no_arg(exit_stack):
    _test_command_passing([r'C:\Windows\System32\whoami.exe'], 0, exit_stack)


def test_command_passing_args_cdb_no_arg(exit_stack):
    _test_command_passing([r'C:\Program Files (x86)\Windows Kits\10\Debuggers\x64\cdb.exe'], 0x80070002, exit_stack)


def test_command_passing_args_cdb_arg(exit_stack):
    _test_command_passing([r'C:\Program Files (x86)\Windows Kits\10\Debuggers\x64\cdb.exe', '-version'], 0, exit_stack)


def test_command_passing_args_cdb_arg_with_space(exit_stack):
    _test_command_passing([r'C:\Program Files (x86)\Windows Kits\10\Debuggers\x64\cdb.exe', '-version', '-z x'], 0, exit_stack)


def test_command_passing_unquoted_echo_no_arg(exit_stack):
    _test_command_passing('echo', 0, exit_stack)


def test_command_passing_unquoted_echo_arg(exit_stack):
    _test_command_passing('echo hello', 0, exit_stack)


def test_command_passing_unquoted_echo_arg_with_space(exit_stack):
    _test_command_passing('echo "hello world"', 0, exit_stack)


def test_command_passing_unquoted_whoami_no_arg(exit_stack):
    _test_command_passing('whoami', 0, exit_stack)


def test_command_passing_unquoted_whoami_full_path_no_arg(exit_stack):
    _test_command_passing(r'C:\Windows\System32\whoami.exe', 0, exit_stack)


def test_command_passing_unquoted_cdb_no_arg(exit_stack):
    _test_command_passing(r'C:\Program Files (x86)\Windows Kits\10\Debuggers\x64\cdb.exe', 0x80070002, exit_stack)


def test_command_passing_quoted_whoami_full_path_no_arg(exit_stack):
    _test_command_passing(r'"C:\Windows\System32\whoami.exe"', 0, exit_stack)


def test_command_passing_quoted_cdb_no_arg(exit_stack):
    _test_command_passing(r'"C:\Program Files (x86)\Windows Kits\10\Debuggers\x64\cdb.exe"', 0x80070002, exit_stack)


def test_command_passing_quoted_cdb_arg(exit_stack):
    _test_command_passing(r'"C:\Program Files (x86)\Windows Kits\10\Debuggers\x64\cdb.exe" -version', 0, exit_stack)


def test_command_passing_quoted_cdb_arg_with_space(exit_stack):
    _test_command_passing(r'"C:\Program Files (x86)\Windows Kits\10\Debuggers\x64\cdb.exe" -version "-z x"', 0, exit_stack)


def _test_command_passing(command, expected_exit_status, exit_stack):
    windows_vm = exit_stack.enter_context(windows_vm_running())
    winrm_shell = WinRMShell(windows_vm.os_access.winrm)
    with winrm_shell.Popen(command) as run:
        stdout_bytes, stderr_bytes = run.communicate()
        assert run.returncode == expected_exit_status
        assert stdout_bytes
        assert not stderr_bytes


def test_command_timeout(exit_stack):
    windows_vm = exit_stack.enter_context(windows_vm_running())
    winrm_shell = WinRMShell(windows_vm.os_access.winrm)
    command = ['ping', '-n', '10', '127.0.0.1']
    with assert_raises(SubprocessError):
        with winrm_shell.Popen(command) as run:
            run.communicate(timeout_sec=1)


def test_exception_while_popen(exit_stack):
    windows_vm = exit_stack.enter_context(windows_vm_running())
    winrm_shell = WinRMShell(windows_vm.os_access.winrm)

    class WhateverError(Exception):
        pass

    command = ['ping', '-n', '10', '127.0.0.1']
    try:
        with winrm_shell.Popen(command) as run:
            raise WhateverError("DoesNotMatter")
    except WhateverError:
        assert isinstance(run.wait(), int)


def test_popen_timeout_at_exit(exit_stack):
    windows_vm = exit_stack.enter_context(windows_vm_running())
    winrm_shell = WinRMShell(windows_vm.os_access.winrm)
    timeout = 4
    command = ['ping', '-n', str(timeout * 2), '127.0.0.1']
    match = f"Command {shlex.join(command)} was working when __exit__ called, kill attempted, successfully stopped"
    with assert_raises_with_message(SubprocessError, match):
        with winrm_shell.Popen(command):
            pass
