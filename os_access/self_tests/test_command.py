# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import binascii
import os
import signal
import time
from contextlib import contextmanager

from directories import get_run_dir
from os_access import Run
from os_access._winrm import STATUS_CONTROL_C_EXIT
from os_access.local_shell import local_shell
from vm.default_vm_pool import public_default_vm_pool
from vm.default_vm_pool import vm_types


@contextmanager
def _run_cls(run_type, artifacts_dir) -> Run:
    vm_pool = public_default_vm_pool(artifacts_dir)
    if run_type == 'local':
        yield local_shell.Popen(['cat'])
    elif run_type == 'win11':
        with vm_pool.clean_vm(vm_types['win11']) as windows_vm:
            windows_vm.os_access.wait_ready()
            with windows_vm.os_access.prepared_one_shot_vm(artifacts_dir):
                with windows_vm.os_access.Popen(['more']) as run:
                    yield run
    elif run_type == 'ssh':
        with vm_pool.clean_vm(vm_types['ubuntu18']) as linux_vm:
            linux_vm.os_access.wait_ready()
            with linux_vm.os_access.prepared_one_shot_vm(artifacts_dir):
                with linux_vm.os_access.shell.Popen(['cat']) as run:
                    yield run
    elif run_type == 'ssh_terminal':
        with vm_pool.clean_vm(vm_types['ubuntu18']) as linux_vm:
            linux_vm.os_access.wait_ready()
            with linux_vm.os_access.prepared_one_shot_vm(artifacts_dir):
                with linux_vm.os_access.shell.Popen(['cat'], terminal=True) as run:
                    yield run
    else:
        raise RuntimeError(f"Unsupported run type: {run_type}")


def test_terminate_local():
    _test_terminate('local')


def test_terminate_ssh_terminal():
    _test_terminate('ssh_terminal')


def test_terminate_win11():
    _test_terminate('win11')


def _test_terminate(run_type):
    artifacts_dir = get_run_dir()
    with _run_cls(run_type, artifacts_dir) as run:
        time.sleep(1)  # Allow command to warm up. Matters on Windows.
        run.terminate()
        run.communicate(timeout_sec=5)
        assert run.returncode in {
            -signal.SIGINT, -signal.SIGTERM,  # Python subprocess feature.
            128 + signal.SIGINT, 128 + signal.SIGTERM,  # Bash-Scripting guide.
            STATUS_CONTROL_C_EXIT,  # Windows status code.
            }
    # TODO: Pseudo-terminal echoes commands, and that's OK. Is there a way to leave command output only?


def test_interaction_local():
    _test_interaction('local')


def test_interaction_ssh():
    _test_interaction('ssh')


def test_interaction_win11():
    _test_interaction('win11')


def _test_interaction(run_type):
    artifacts_dir = get_run_dir()
    with _run_cls(run_type, artifacts_dir) as run:
        run.send(b'qwe\n')
        # TODO: Make `expect` method which expects bytes on stdout to avoid dumb waits.
        time.sleep(.1)  # Let command to receive and send data back.
        stdout, _ = run.receive(10)
        assert run.returncode is None
        assert stdout.rstrip(b'\r\n') == b'qwe'
        run.send(b'asd\n', is_last=True)
        time.sleep(.1)  # Let command to receive and send data back.
        stdout, _ = run.receive(10)
        assert run.returncode is not None
        assert run.returncode == 0
        assert stdout.rstrip(b'\r\n') == b'asd'


def test_much_data_and_exit_local():
    _test_much_data_and_exit('local')


def test_much_data_and_exit_ssh():
    _test_much_data_and_exit('ssh')


def test_much_data_and_exit_win11():
    _test_much_data_and_exit('win11')


def _test_much_data_and_exit(run_type):
    artifacts_dir = get_run_dir()
    with _run_cls(run_type, artifacts_dir) as run:
        data = binascii.hexlify(os.urandom(10000))
        stdout, stderr = run.communicate(input=data, timeout_sec=5000)
        assert stdout.rstrip(b'\r\n') == data
