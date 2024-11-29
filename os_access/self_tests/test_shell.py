# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import os
import re
import shlex
import sys
import time
from contextlib import contextmanager
from subprocess import CalledProcessError
from subprocess import SubprocessError
from subprocess import TimeoutExpired

from directories import get_run_dir
from os_access import PosixAccess
from os_access import WindowsAccess
from os_access._winrm_shell import WinRMShell
from os_access.local_shell import local_shell
from tests.infra import Failure
from tests.infra import Skip
from tests.infra import assert_raises
from tests.infra import assert_raises_with_message
from vm.default_vm_pool import public_default_vm_pool
from vm.default_vm_pool import vm_types

_logger = logging.getLogger(__name__)


@contextmanager
def make_shell(shell_type):
    if shell_type.startswith('local-'):
        yield local_shell
    else:
        artifacts_dir = get_run_dir()
        vm_pool = public_default_vm_pool(artifacts_dir)
        if shell_type == 'ssh':
            with vm_pool.clean_vm(vm_types['ubuntu18']) as linux_vm:
                linux_vm.os_access.wait_ready()
                with linux_vm.os_access.prepared_one_shot_vm(artifacts_dir):
                    assert isinstance(linux_vm.os_access, PosixAccess)
                    yield linux_vm.os_access.shell
        elif shell_type == 'winrm':
            with vm_pool.clean_vm(vm_types['win11']) as windows_vm:
                windows_vm.os_access.wait_ready()
                with windows_vm.os_access.prepared_one_shot_vm(artifacts_dir):
                    assert isinstance(windows_vm.os_access, WindowsAccess)
                    yield WinRMShell(windows_vm.os_access.winrm)
        else:
            raise ValueError(f"Unsupported shell type: {shell_type}")


def find_python(shell):
    if shell is local_shell:
        return sys.executable
    try:
        shell.run(['python', '-V'])
    except CalledProcessError as e:
        raise Skip(f"python executable not found on {shell}: {e}")
    return 'python'


def test_run_command_ssh(exit_stack):
    _test_run_command('ssh', exit_stack)


if os.name == 'posix':
    def test_run_command_local_posix(exit_stack):
        _test_run_command('local-posix', exit_stack)


def _test_run_command(shell_type, exit_stack):
    shell = exit_stack.enter_context(make_shell(shell_type))
    given = b'It works! \n\t$`{}[]()\'\"\\'
    result = shell.run(['echo', '-n', given.decode()])
    assert result.stdout == given


def test_print_stderr_ssh(exit_stack):
    _test_print_stderr('ssh', exit_stack)


if os.name == 'posix':
    def test_print_stderr_local_posix(exit_stack):
        _test_print_stderr('local-posix', exit_stack)


def test_print_stderr_winrm(exit_stack):
    _test_print_stderr('winrm', exit_stack)


def _test_print_stderr(shell_type, exit_stack):
    shell = exit_stack.enter_context(make_shell(shell_type))
    if shell_type == 'winrm':
        cmd = ['route', '/nonexistent']
        awaited_stderr = 'ROUTE [-f] [-p] [-4|-6] command [destination]'
    else:
        cmd = ['cat', '/nonexistent']
        awaited_stderr = 'cat: /nonexistent: No such file or directory'
    try:
        shell.run(cmd)
    except CalledProcessError as err:
        exception_as_string = str(err)
        _logger.info("Got exception: %s", exception_as_string)
        assert awaited_stderr in exception_as_string
    else:
        raise Failure(f"CMD {cmd} must fail, but it passed.")


def test_run_command_with_input_ssh(exit_stack):
    _test_run_command_with_input('ssh', exit_stack)


if os.name == 'posix':
    def test_run_command_with_input_local_posix(exit_stack):
        _test_run_command_with_input('local-posix', exit_stack)


def test_run_command_with_input_winrm(exit_stack):
    _test_run_command_with_input('winrm', exit_stack)


def _test_run_command_with_input(shell_type, exit_stack):
    shell = exit_stack.enter_context(make_shell(shell_type))
    given = b'It works!'
    result = shell.run(['cat'], input=given)
    assert result.stdout == given


def test_run_script_ssh(exit_stack):
    _test_run_script('ssh', exit_stack)


if os.name == 'posix':
    def test_run_script_local_posix(exit_stack):
        _test_run_script('local-posix', exit_stack)


def _test_run_script(shell_type, exit_stack):
    shell = exit_stack.enter_context(make_shell(shell_type))
    given = b'It works!'
    received = shell.run('echo ' + given.decode())
    assert received.stdout.rstrip() == given


def test_non_zero_exit_code_ssh(exit_stack):
    _test_non_zero_exit_code('ssh', exit_stack)


if os.name == 'posix':
    def test_non_zero_exit_code_local_posix(exit_stack):
        _test_non_zero_exit_code('local-posix', exit_stack)


def _test_non_zero_exit_code(shell_type, exit_stack):
    shell = exit_stack.enter_context(make_shell(shell_type))
    random_exit_status = 42
    try:
        shell.run('exit {}'.format(random_exit_status))
    except CalledProcessError as e:
        assert e.returncode == random_exit_status
    else:
        raise Exception("Did not raise")


def test_timeout_ssh(exit_stack):
    _test_timeout('ssh', exit_stack)


if os.name == 'posix':
    def test_timeout_local_posix(exit_stack):
        _test_timeout('local-posix', exit_stack)


def _test_timeout(shell_type, exit_stack):
    shell = exit_stack.enter_context(make_shell(shell_type))
    with assert_raises(TimeoutExpired):
        shell.run(['sleep', 60], timeout_sec=1)


# language=Python
_forked_child_script = '''
import os
import sys
import time

if __name__ == '__main__':
    sleep_time_sec = int(sys.argv[1])

    if os.fork():
        print("Parent process, finished.")
    else:
        print("Child process, sleeping for {:d} seconds...".format(sleep_time_sec))
        sys.stdout.flush()
        time.sleep(sleep_time_sec)
        print("Child process, finished.")
'''


def test_streams_left_open_ssh(exit_stack):
    _test_streams_left_open('ssh', exit_stack)


if os.name == 'posix':
    def test_streams_left_open_local_posix(exit_stack):
        _test_streams_left_open('local-posix', exit_stack)


def _test_streams_left_open(shell_type, exit_stack):
    shell = exit_stack.enter_context(make_shell(shell_type))
    python_executable = find_python(shell)
    sleep_time_sec = 60
    start_time = time.monotonic()
    shell.run([python_executable, '-c', _forked_child_script, sleep_time_sec], timeout_sec=5)
    assert time.monotonic() - start_time < sleep_time_sec


# language=Python
_early_closing_streams_script = '''
import sys
import time

if __name__ == '__main__':
    sleep_time_sec = int(sys.argv[1])
    sys.stdout.write("Test data on stdout.")
    sys.stderr.write("Test data on stderr.")
    sys.stdout.close()
    sys.stderr.close()
    time.sleep(sleep_time_sec)
'''


def test_streams_closed_early_but_process_timed_out_ssh(exit_stack):
    _test_streams_closed_early_but_process_timed_out('ssh', exit_stack)


if os.name == 'posix':
    def test_streams_closed_early_but_process_timed_out_local_posix(exit_stack):
        _test_streams_closed_early_but_process_timed_out('local-posix', exit_stack)


def _test_streams_closed_early_but_process_timed_out(shell_type, exit_stack):
    shell = exit_stack.enter_context(make_shell(shell_type))
    python_executable = find_python(shell)
    with assert_raises(TimeoutExpired):
        shell.run([python_executable, '-c', _early_closing_streams_script, 5], timeout_sec=2)


def test_streams_closed_early_and_process_on_time_ssh(exit_stack):
    _test_streams_closed_early_and_process_on_time('ssh', exit_stack)


if os.name == 'posix':
    def test_streams_closed_early_and_process_on_time_local_posix(exit_stack):
        _test_streams_closed_early_and_process_on_time('local-posix', exit_stack)


def _test_streams_closed_early_and_process_on_time(shell_type, exit_stack):
    shell = exit_stack.enter_context(make_shell(shell_type))
    python_executable = find_python(shell)
    shell.run([python_executable, '-c', _early_closing_streams_script, 2], timeout_sec=5)


# language=Python
_wait_for_any_data_script = r'''import sys; sys.stdin.read(1)'''


def test_receive_times_out_ssh(exit_stack):
    _test_receive_times_out('ssh', exit_stack)


if os.name == 'posix':
    def test_receive_times_out_local_posix(exit_stack):
        _test_receive_times_out('local-posix', exit_stack)


def test_receive_times_out_winrm(exit_stack):
    _test_receive_times_out('winrm', exit_stack)


def _test_receive_times_out(shell_type, exit_stack):
    shell = exit_stack.enter_context(make_shell(shell_type))
    python_executable = find_python(shell)
    acceptable_error_sec = 0.4
    timeout_sec = 2
    with shell.Popen([python_executable, '-c', _wait_for_any_data_script]) as run:
        while True:
            begin = time.perf_counter()
            output_line, stderr = run.receive(timeout_sec)
            end = time.perf_counter()
            assert output_line == b''
            if stderr == b'':
                break
        assert timeout_sec < end - begin < timeout_sec + acceptable_error_sec
        _, _ = run.communicate(input=b' ', timeout_sec=2)
        assert run.returncode == 0


# language=Python
_delayed_cat = r'''
import sys
import time

if __name__ == '__main__':
    sleep_time_sec = float(sys.argv[1])
    while True:
        line = sys.stdin.readline()
        if line == '\n':
            break
        time.sleep(sleep_time_sec)
        sys.stdout.write(line)
        sys.stdout.flush()
'''


def test_receive_with_delays_ssh(exit_stack):
    _test_receive_with_delays('ssh', exit_stack)


if os.name == 'posix':
    def test_receive_with_delays_local_posix(exit_stack):
        _test_receive_with_delays('local-posix', exit_stack)


def _test_receive_with_delays(shell_type, exit_stack):
    shell = exit_stack.enter_context(make_shell(shell_type))
    python_executable = find_python(shell)
    delay_sec = 2
    vm_time_error_sec = 0.05
    acceptable_error_sec = 0.1
    timeout_tolerance_sec = 0.2
    with shell.Popen([python_executable, '-c', _delayed_cat, delay_sec]) as run:
        while True:
            stdout, stderr = run.receive(delay_sec + timeout_tolerance_sec)
            assert not stdout
            if not stderr:
                break
        second_begin = time.monotonic()
        input_line = b'test line\n'
        run.send(input_line)
        second_output_line, second_stderr = run.receive(delay_sec + timeout_tolerance_sec)
        second_check = time.monotonic()
        assert second_stderr == b''
        assert second_output_line == input_line
        assert delay_sec - vm_time_error_sec < second_check - second_begin
        assert second_check - second_begin < delay_sec + acceptable_error_sec
        run.communicate(b'\n', delay_sec + timeout_tolerance_sec)
        assert run.returncode == 0


def test_terminal_large_command_line_10(exit_stack):
    _test_terminal_large_command_line(10, exit_stack)


def test_terminal_large_command_line_1k(exit_stack):
    _test_terminal_large_command_line(1024, exit_stack)


def test_terminal_large_command_line_10k(exit_stack):
    _test_terminal_large_command_line(10 * 1024, exit_stack)


def test_terminal_large_command_line_20k(exit_stack):
    _test_terminal_large_command_line(20 * 1024, exit_stack)


def test_terminal_large_command_line_30k(exit_stack):
    _test_terminal_large_command_line(30 * 1024, exit_stack)


def test_terminal_large_command_line_40k(exit_stack):
    _test_terminal_large_command_line(40 * 1024, exit_stack)


def test_terminal_large_command_line_50k(exit_stack):
    _test_terminal_large_command_line(50 * 1024, exit_stack)


def test_terminal_large_command_line_100k(exit_stack):
    _test_terminal_large_command_line(100 * 1024, exit_stack)


def _test_terminal_large_command_line(size: int, exit_stack):
    ssh = exit_stack.enter_context(make_shell('ssh'))
    timeout_sec = 900
    data = ''.join(str(i % 10) for i in range(size))  # '01234567890123...'
    command = f'echo -n {shlex.quote(data)} | wc --chars | xargs -IX echo "<X>"'
    with ssh.Popen(command, terminal=True) as run:
        try:
            stdout, stderr = run.communicate(timeout_sec=timeout_sec)
        except TimeoutExpired as e:
            stdout = e.stdout
            stderr = e.stderr

    _logger.info("stdout:\n%s", stdout.decode())
    _logger.info("stderr:\n%s", stderr.decode())
    mo = re.search(rb'<(\d+)>', stdout)
    if not mo:
        raise Failure(f"Expected byte count is not received in {timeout_sec} seconds from 'wc' command.")
    assert not stderr
    assert mo and int(mo.group(1)) == len(data)  # All data should be fed to wc


def test_failing_terminal_command_direct(exit_stack):
    _test_failing_terminal_command(False, exit_stack)


def test_failing_terminal_command_terminal(exit_stack):
    _test_failing_terminal_command(True, exit_stack)


def _test_failing_terminal_command(use_terminal: bool, exit_stack):
    ssh = exit_stack.enter_context(make_shell('ssh'))
    command = ['ls', '--invalid-option']
    with ssh.Popen(command, terminal=use_terminal) as run:
        stdout = b''
        stderr = b''
        t = time.monotonic()
        timeout_sec = 10
        while time.monotonic() - t < timeout_sec:
            returncode = run.returncode
            out, err = run.receive(timeout_sec=2)
            if out:
                stdout += out
            if err:
                stderr += err
            if returncode is not None:
                break

    _logger.info("stdout:\n%s", stdout.decode())
    _logger.info("stderr:\n%s", stderr.decode())
    _logger.info("returncode: %d", run.returncode)
    assert run.returncode == 2
    assert b'ls: unrecognized option' in stdout if use_terminal else stderr


def test_exception_while_popen_direct(exit_stack):
    _test_exception_while_popen(False, exit_stack)


def test_exception_while_popen_terminal(exit_stack):
    _test_exception_while_popen(True, exit_stack)


def _test_exception_while_popen(use_terminal: bool, exit_stack):
    ssh = exit_stack.enter_context(make_shell('ssh'))

    class WhateverError(Exception):
        pass

    command = ['sleep', '2']
    try:
        with ssh.Popen(command, terminal=use_terminal) as run:
            raise WhateverError("DoesNotMatter")
    except WhateverError:
        assert isinstance(run.wait(), int)


def test_popen_still_running_direct(exit_stack):
    _test_popen_still_running(False, exit_stack)


def test_popen_still_running_terminal(exit_stack):
    _test_popen_still_running(True, exit_stack)


def _test_popen_still_running(use_terminal: bool, exit_stack):
    ssh = exit_stack.enter_context(make_shell('ssh'))
    command = ['sleep', '2']
    with assert_raises(SubprocessError):
        with ssh.Popen(command, terminal=use_terminal):
            pass


def test_popen_stopped_at_exit_interactive(exit_stack):
    ssh = exit_stack.enter_context(make_shell('ssh'))
    timeout = 3
    command = ['sleep', str(timeout * 2)]
    match = f"Command {shlex.join(command)} was working when __exit__ called, kill attempted, successfully stopped"
    with assert_raises_with_message(SubprocessError, match):
        with ssh.Popen(command, terminal=True) as run:
            run._defensive_timeout = timeout


def test_popen_timeout_at_exit_nointeractive(exit_stack):
    ssh = exit_stack.enter_context(make_shell('ssh'))
    timeout = 3
    command = ['sleep', str(timeout * 2)]
    match = f"Command {shlex.join(command)} was working when __exit__ called, kill not implemented, timed out"
    with assert_raises_with_message(SubprocessError, match):
        with ssh.Popen(command, terminal=False) as run:
            run._defensive_timeout = timeout


def test_popen_runtime_at_exit_nointeractive(exit_stack):
    ssh = exit_stack.enter_context(make_shell('ssh'))
    timeout = 3
    command = ['sleep', str(timeout * 2)]
    match = f"Command {shlex.join(command)} was working when __exit__ called, kill not implemented, successfully stopped"
    with assert_raises_with_message(SubprocessError, match):
        with ssh.Popen(command, terminal=False):
            pass
