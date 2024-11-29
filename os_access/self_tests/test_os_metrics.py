# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time
from contextlib import ExitStack

from directories import get_run_dir
from installation import OsCollectingMetrics
from os_access import WindowsAccess
from os_access.windows_graphic_app import start_in_graphic_mode
from vm.default_vm_pool import public_default_vm_pool
from vm.default_vm_pool import vm_types


def test_os_metrics_win11(exit_stack: ExitStack):
    test_os_metrics(exit_stack, 'win11')


def test_os_metrics_ubuntu20(exit_stack: ExitStack):
    test_os_metrics(exit_stack, 'ubuntu20')


def test_os_metrics(exit_stack: ExitStack, os_name: str):
    artifacts_dir = get_run_dir()
    vm_pool = public_default_vm_pool(artifacts_dir)
    vm = exit_stack.enter_context(vm_pool.clean_vm(vm_types[os_name]))
    vm.ensure_started(artifacts_dir)
    exit_stack.enter_context(vm.os_access.prepared_one_shot_vm(artifacts_dir))
    os_metrics = OsCollectingMetrics(vm.os_access)
    time.sleep(0.1)  # There needs to be a little time between starting metrics and taking the first measurement
    started_at = time.monotonic()
    while True:  # Wait until the operating system has fully started
        start_metrics = os_metrics.get_current()
        if start_metrics['cpu_usage'] < 0.2:
            break
        if time.monotonic() - started_at > 30:
            raise RuntimeError("CPU usage is too high")
        time.sleep(1)
    _logger.info("Start metrics: %s", start_metrics)
    _logger.info("CPU usage: %r", start_metrics['cpu_usage'])
    # Run tar as a separate process
    if isinstance(vm.os_access, WindowsAccess):
        start_in_graphic_mode(vm.os_access, ['tar', '-cvzf', 'c:/archive.tar.gz', 'c:/Program Files'])
    else:
        ssh_run = vm.os_access.shell.Popen(['tar', '-cvzf', '/var/archive.tar.gz', '/usr'])
        exit_stack.callback(ssh_run.close)
    time.sleep(2)
    metrics = os_metrics.get_current()
    _logger.info("Current metrics: %s", metrics)
    _logger.info("CPU usage: %r", metrics['cpu_usage'])
    assert start_metrics != metrics
    assert 0.2 <= metrics['cpu_usage'] <= 1
    assert metrics['disk']['name'] != ''
    assert metrics['disk']['read_bytes'] > 0
    assert metrics['disk']['write_bytes'] > 0
    assert metrics['disk']['reading_sec'] > 0
    assert metrics['disk']['writing_sec'] > 0
    assert metrics['disk']['read_count'] > 0
    assert metrics['disk']['write_count'] > 0
    assert metrics['disk']['iops_read'] > 0
    assert metrics['disk']['iops_write'] > 0
    assert metrics['disk']['iops_bytes_read'] > 0
    assert metrics['disk']['iops_bytes_write'] > 0
    assert metrics['drive'][0] == metrics['disk']


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    _logger = logging.getLogger(__name__)
    with ExitStack() as stack:
        test_os_metrics_win11(stack)
        test_os_metrics_ubuntu20(stack)
