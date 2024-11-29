# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import hashlib
import math
import os
import time
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from subprocess import CalledProcessError
from subprocess import TimeoutExpired

from directories import get_run_dir
from os_access import Networking
from os_access import Ssh
from os_access._winrm import WinRM
from os_access._winrm_shell import WinRMShell
from tests.infra import Skip
from tests.infra import assert_raises
from tests.infra import assert_raises_with_message_re
from vm.default_vm_pool import public_default_vm_pool
from vm.default_vm_pool import vm_types


def test_run_command_ubuntu18(exit_stack):
    _test_run_command('ubuntu18', exit_stack)


def test_run_command_win11(exit_stack):
    _test_run_command('win11', exit_stack)


def _test_run_command(one_vm_type, exit_stack):
    artifacts_dir = get_run_dir()
    vm_pool = public_default_vm_pool(artifacts_dir)
    one_vm = exit_stack.enter_context(vm_pool.clean_vm(vm_types[one_vm_type]))
    one_vm.ensure_started(artifacts_dir)
    exit_stack.enter_context(one_vm.os_access.prepared_one_shot_vm(artifacts_dir))
    exit_stack.enter_context(one_vm.os_access.traffic_capture_collector(artifacts_dir))
    os_access = one_vm.os_access
    result = os_access.run(['whoami'])
    assert result.stdout  # I.e. something is returned.


def test_is_ready_ubuntu18(exit_stack):
    _test_is_ready('ubuntu18', exit_stack)


def test_is_ready_win11(exit_stack):
    _test_is_ready('win11', exit_stack)


def _test_is_ready(one_vm_type, exit_stack):
    artifacts_dir = get_run_dir()
    vm_pool = public_default_vm_pool(artifacts_dir)
    one_vm = exit_stack.enter_context(vm_pool.clean_vm(vm_types[one_vm_type]))
    one_vm.ensure_started(artifacts_dir)
    exit_stack.enter_context(one_vm.os_access.prepared_one_shot_vm(artifacts_dir))
    exit_stack.enter_context(one_vm.os_access.traffic_capture_collector(artifacts_dir))
    os_access = one_vm.os_access
    assert isinstance(os_access.is_ready(), bool)


def test_reboot_ubuntu18(exit_stack):
    _test_reboot('ubuntu18', exit_stack)


def test_reboot_win11(exit_stack):
    _test_reboot('win11', exit_stack)


def _test_reboot(one_vm_type, exit_stack):
    artifacts_dir = get_run_dir()
    vm_pool = public_default_vm_pool(artifacts_dir)
    one_vm = exit_stack.enter_context(vm_pool.clean_vm(vm_types[one_vm_type]))
    one_vm.ensure_started(artifacts_dir)
    exit_stack.enter_context(one_vm.os_access.prepared_one_shot_vm(artifacts_dir))
    exit_stack.enter_context(one_vm.os_access.traffic_capture_collector(artifacts_dir))
    os_access = one_vm.os_access
    os_access.reboot()
    assert os_access.is_ready()
    # Check that SMB works after reboot.
    path = os_access.tmp().joinpath('test_after_reboot.txt')
    path.parent.mkdir(exist_ok=True, parents=True)
    path.write_bytes(b'hello')
    assert path.stat().st_size == 5


def test_networking_ubuntu18(exit_stack):
    _test_networking('ubuntu18', exit_stack)


def test_networking_win11(exit_stack):
    _test_networking('win11', exit_stack)


def _test_networking(one_vm_type, exit_stack):
    artifacts_dir = get_run_dir()
    vm_pool = public_default_vm_pool(artifacts_dir)
    one_vm = exit_stack.enter_context(vm_pool.clean_vm(vm_types[one_vm_type]))
    one_vm.ensure_started(artifacts_dir)
    exit_stack.enter_context(one_vm.os_access.prepared_one_shot_vm(artifacts_dir))
    exit_stack.enter_context(one_vm.os_access.traffic_capture_collector(artifacts_dir))
    os_access = one_vm.os_access
    assert isinstance(os_access.networking, Networking)
    assert os_access.networking is os_access.networking  # I.e. same class returned each time.


def test_get_set_time_ubuntu18(exit_stack):
    _test_get_set_time('ubuntu18', exit_stack)


def test_get_set_time_win11(exit_stack):
    _test_get_set_time('win11', exit_stack)


def _test_get_set_time(one_vm_type, exit_stack):
    artifacts_dir = get_run_dir()
    vm_pool = public_default_vm_pool(artifacts_dir)
    one_vm = exit_stack.enter_context(vm_pool.clean_vm(vm_types[one_vm_type]))
    one_vm.ensure_started(artifacts_dir)
    exit_stack.enter_context(one_vm.os_access.prepared_one_shot_vm(artifacts_dir))
    exit_stack.enter_context(one_vm.os_access.traffic_capture_collector(artifacts_dir))
    os_access = one_vm.os_access
    os_access.get_datetime()
    os_access.set_datetime(datetime.now(timezone.utc) - timedelta(days=100))


def test_disk_space_ubuntu18(exit_stack):
    _test_disk_space('ubuntu18', exit_stack)


def test_disk_space_win11(exit_stack):
    _test_disk_space('win11', exit_stack)


def _test_disk_space(one_vm_type, exit_stack):
    artifacts_dir = get_run_dir()
    vm_pool = public_default_vm_pool(artifacts_dir)
    one_vm = exit_stack.enter_context(vm_pool.clean_vm(vm_types[one_vm_type]))
    one_vm.ensure_started(artifacts_dir)
    exit_stack.enter_context(one_vm.os_access.prepared_one_shot_vm(artifacts_dir))
    exit_stack.enter_context(one_vm.os_access.traffic_capture_collector(artifacts_dir))
    os_access = one_vm.os_access
    should_be = 1000 * 1000 * 1000
    free_min_threshold = 5 * 1024 * 1024
    free_max_threshold = should_be + 5 * 1024 * 1024
    if os_access.system_disk().free < should_be:
        message = "Too low on space, need {} MB".format(should_be / 1024 / 1024)
        raise Skip(message)
    os_access.maintain_free_disk_space(should_be)
    assert free_min_threshold < os_access.system_disk().free < free_max_threshold
    os_access.clean_up_disk_space()
    assert os_access.system_disk().free > should_be


def test_disk_space_limit_twice_ubuntu18(exit_stack):
    _test_disk_space_limit_twice('ubuntu18', exit_stack)


def test_disk_space_limit_twice_win11(exit_stack):
    _test_disk_space_limit_twice('win11', exit_stack)


def _test_disk_space_limit_twice(one_vm_type, exit_stack):
    artifacts_dir = get_run_dir()
    vm_pool = public_default_vm_pool(artifacts_dir)
    one_vm = exit_stack.enter_context(vm_pool.clean_vm(vm_types[one_vm_type]))
    one_vm.ensure_started(artifacts_dir)
    exit_stack.enter_context(one_vm.os_access.prepared_one_shot_vm(artifacts_dir))
    exit_stack.enter_context(one_vm.os_access.traffic_capture_collector(artifacts_dir))
    os_access = one_vm.os_access
    should_be_1 = 1000 * 1000 * 1000
    free_min_threshold_1 = 5 * 1024 * 1024
    free_max_threshold_1 = should_be_1 + 5 * 1024 * 1024
    if os_access.system_disk().free < should_be_1:
        message = "Too low on space, need {} MB".format(should_be_1 / 1024 / 1024)
        raise Skip(message)
    os_access.maintain_free_disk_space(should_be_1)
    assert free_min_threshold_1 < os_access.system_disk().free < free_max_threshold_1
    should_be_2 = 500 * 1000 * 1000
    free_min_threshold_2 = 5 * 1024 * 1024
    free_max_threshold_2 = should_be_1 + 5 * 1024 * 1024
    assert should_be_2 < should_be_1
    os_access.maintain_free_disk_space(should_be_2)
    assert free_min_threshold_2 < os_access.system_disk().free < free_max_threshold_2
    os_access.clean_up_disk_space()
    assert os_access.system_disk().free > should_be_1


def test_fake_disk_twice_ubuntu18_small_big(exit_stack):
    _test_fake_disk_twice('ubuntu18', (500 * 10**6, 700 * 10**9), exit_stack)


def test_fake_disk_twice_win11_small_big(exit_stack):
    _test_fake_disk_twice('win11', (500 * 10**6, 700 * 10**9), exit_stack)


def test_fake_disk_twice_ubuntu18_big_small(exit_stack):
    _test_fake_disk_twice('ubuntu18', (700 * 10**9, 500 * 10**6), exit_stack)


def test_fake_disk_twice_win11_big_small(exit_stack):
    _test_fake_disk_twice('win11', (700 * 10**9, 500 * 10**6), exit_stack)


def _test_fake_disk_twice(one_vm_type, disk_sizes, exit_stack):
    artifacts_dir = get_run_dir()
    vm_pool = public_default_vm_pool(artifacts_dir)
    one_vm = exit_stack.enter_context(vm_pool.clean_vm(vm_types[one_vm_type]))
    one_vm.ensure_started(artifacts_dir)
    exit_stack.enter_context(one_vm.os_access.prepared_one_shot_vm(artifacts_dir))
    exit_stack.enter_context(one_vm.os_access.traffic_capture_collector(artifacts_dir))
    os_access = one_vm.os_access
    size_1, size_2 = disk_sizes
    path = os_access.mount_fake_disk('V', size_1)
    disk = os_access.volumes()[path]
    assert math.isclose(disk.total, size_1, rel_tol=0.02)
    os_access.dismount_fake_disk(path)
    path = os_access.mount_fake_disk('V', size_2)
    disk = os_access.volumes()[path]
    assert math.isclose(disk.total, size_2, rel_tol=0.02)


def test_file_md5_ubuntu18(exit_stack):
    _test_file_md5('ubuntu18', exit_stack)


def test_file_md5_win11(exit_stack):
    _test_file_md5('win11', exit_stack)


def _test_file_md5(one_vm_type, exit_stack):
    artifacts_dir = get_run_dir()
    vm_pool = public_default_vm_pool(artifacts_dir)
    one_vm = exit_stack.enter_context(vm_pool.clean_vm(vm_types[one_vm_type]))
    one_vm.ensure_started(artifacts_dir)
    exit_stack.enter_context(one_vm.os_access.prepared_one_shot_vm(artifacts_dir))
    exit_stack.enter_context(one_vm.os_access.traffic_capture_collector(artifacts_dir))
    os_access = one_vm.os_access
    path = os_access.tmp() / 'test_file_md5.txt'
    data = os.urandom(100500)
    path.write_bytes(data)
    assert os_access.file_md5(path) == hashlib.md5(data).hexdigest()


def test_folder_contents_size_ubuntu18(exit_stack):
    _test_folder_contents_size('ubuntu18', exit_stack)


def test_folder_contents_size_win11(exit_stack):
    _test_folder_contents_size('win11', exit_stack)


def _test_folder_contents_size(one_vm_type, exit_stack):
    artifacts_dir = get_run_dir()
    vm_pool = public_default_vm_pool(artifacts_dir)
    one_vm = exit_stack.enter_context(vm_pool.clean_vm(vm_types[one_vm_type]))
    one_vm.ensure_started(artifacts_dir)
    exit_stack.enter_context(one_vm.os_access.prepared_one_shot_vm(artifacts_dir))
    exit_stack.enter_context(one_vm.os_access.traffic_capture_collector(artifacts_dir))
    os_access = one_vm.os_access
    root = os_access.tmp() / 'root'
    sub_folder_1 = root / 'sub_folder_1'
    sub_folder_2 = root / 'sub_folder_2'
    sub_folder_3 = sub_folder_1 / 'sub_folder_3'
    sub_folder_4 = sub_folder_2 / 'sub_folder_4'
    root.rmtree(ignore_errors=True)
    root.mkdir()
    sub_folder_1.mkdir()
    sub_folder_2.mkdir()
    sub_folder_3.mkdir()
    sub_folder_4.mkdir()
    os_access.create_file(root / 'file_20', 20 * 1024**2)
    os_access.create_file(sub_folder_1 / 'file_10', 10 * 1024**2)
    os_access.create_file(sub_folder_2 / 'file_20', 20 * 1024**2)
    os_access.create_file(sub_folder_3 / 'file_30', 30 * 1024**2)
    os_access.create_file(sub_folder_4 / 'file_40', 40 * 1024**2)

    assert math.isclose(os_access.folder_contents_size(root), 120 * 1024**2, rel_tol=0.01)


# Emulate timeout by ping.
# Both `timeout` and `pause` windows commands expect input and leads to an error:
# `Input redirection is not supported, exiting the process immediately`.
def _sleep_command(sleep_duration):
    return ['ping', '-n', sleep_duration, '127.0.0.1', '>', 'NUL']


def test_command_timeout_not_expired_win11(exit_stack):
    _test_command_timeout_not_expired('win11', exit_stack)


def _test_command_timeout_not_expired(one_vm_type, exit_stack):
    artifacts_dir = get_run_dir()
    vm_pool = public_default_vm_pool(artifacts_dir)
    one_vm = exit_stack.enter_context(vm_pool.clean_vm(vm_types[one_vm_type]))
    one_vm.ensure_started(artifacts_dir)
    exit_stack.enter_context(one_vm.os_access.prepared_one_shot_vm(artifacts_dir))
    exit_stack.enter_context(one_vm.os_access.traffic_capture_collector(artifacts_dir))
    os_access = one_vm.os_access
    os_access.run(_sleep_command(5), timeout_sec=20)


def test_command_timeout_expired_win11(exit_stack):
    _test_command_timeout_expired('win11', exit_stack)


def _test_command_timeout_expired(one_vm_type, exit_stack):
    artifacts_dir = get_run_dir()
    vm_pool = public_default_vm_pool(artifacts_dir)
    one_vm = exit_stack.enter_context(vm_pool.clean_vm(vm_types[one_vm_type]))
    one_vm.ensure_started(artifacts_dir)
    exit_stack.enter_context(one_vm.os_access.prepared_one_shot_vm(artifacts_dir))
    exit_stack.enter_context(one_vm.os_access.traffic_capture_collector(artifacts_dir))
    os_access = one_vm.os_access
    with assert_raises(TimeoutExpired):
        os_access.run(_sleep_command(20), timeout_sec=5)


def test_disks_ubuntu18_usb(exit_stack):
    _test_disks('ubuntu18', 'usb', exit_stack)


def test_disks_win11_usb(exit_stack):
    _test_disks('win11', 'usb', exit_stack)


def test_disks_ubuntu18_sata(exit_stack):
    _test_disks('ubuntu18', 'sata', exit_stack)


def test_disks_win11_sata(exit_stack):
    _test_disks('win11', 'sata', exit_stack)


def _test_disks(one_vm_type, disk_type, exit_stack):
    artifacts_dir = get_run_dir()
    vm_pool = public_default_vm_pool(artifacts_dir)
    one_vm = exit_stack.enter_context(vm_pool.clean_vm(vm_types[one_vm_type]))
    one_vm.ensure_started(artifacts_dir)
    exit_stack.enter_context(one_vm.os_access.prepared_one_shot_vm(artifacts_dir))
    exit_stack.enter_context(one_vm.os_access.traffic_capture_collector(artifacts_dir))
    os_access = one_vm.os_access
    one_vm.vm_control.add_disk(disk_type, 10_000)
    path_p = os_access.mount_disk('P')
    one_vm.vm_control.add_disk(disk_type, 20_000)
    path_q = os_access.mount_disk('Q')
    path_p.joinpath('file').write_bytes(b'data')
    path_q.joinpath('file').write_bytes(b'data')


def _create_sleep_process(shell):
    shell.Popen(['sleep', '10'])
    pid = int(shell.run(['pgrep', 'sleep']).stdout.decode('ascii'))
    return pid


def _kill_safe(shell, pid):
    # In test_process_paused_context_manager we assert
    # that if process was killed while paused,
    # and no inner exception occurred, __exit__ of
    # _process_paused() raises CalledProcessError.
    # But if kill command in test fails, it's
    # test failure, so we raise RuntimeError.
    try:
        shell.run(['kill', '-SIGKILL', pid])
    except CalledProcessError:
        raise RuntimeError('Kill sleep process failed unexpectedly.')


def test_process_paused_context_manager_ubuntu18(exit_stack):
    _test_process_paused_context_manager('ubuntu18', exit_stack)


def _test_process_paused_context_manager(one_vm_type, exit_stack):
    artifacts_dir = get_run_dir()
    vm_pool = public_default_vm_pool(artifacts_dir)
    one_vm = exit_stack.enter_context(vm_pool.clean_vm(vm_types[one_vm_type]))
    one_vm.ensure_started(artifacts_dir)
    exit_stack.enter_context(one_vm.os_access.prepared_one_shot_vm(artifacts_dir))
    exit_stack.enter_context(one_vm.os_access.traffic_capture_collector(artifacts_dir))
    os_access = one_vm.os_access
    shell = os_access.shell
    pid = _create_sleep_process(shell)
    with assert_raises(CalledProcessError):
        with os_access.process_paused(pid):
            _kill_safe(shell, pid)
    # CalledProcessError while trying
    # to unpause already killed process
    # must not suppress previous exception.
    pid = _create_sleep_process(shell)
    with assert_raises(ValueError):
        with os_access.process_paused(pid):
            _kill_safe(shell, pid)
            raise ValueError()
    pid = _create_sleep_process(shell)
    with os_access.process_paused(pid):
        pass


def test_list_total_cpu_usage_ubuntu18(exit_stack):
    _test_list_total_cpu_usage('ubuntu18', exit_stack)


def test_list_total_cpu_usage_win11(exit_stack):
    _test_list_total_cpu_usage('win11', exit_stack)


def _test_list_total_cpu_usage(one_vm_type, exit_stack):
    artifacts_dir = get_run_dir()
    vm_pool = public_default_vm_pool(artifacts_dir)
    one_vm = exit_stack.enter_context(vm_pool.clean_vm(vm_types[one_vm_type]))
    one_vm.ensure_started(artifacts_dir)
    exit_stack.enter_context(one_vm.os_access.prepared_one_shot_vm(artifacts_dir))
    exit_stack.enter_context(one_vm.os_access.traffic_capture_collector(artifacts_dir))
    os_access = one_vm.os_access
    try:
        os_access._start_cpu_load()
        # Delay for CPU usage to change
        time.sleep(5)
        usages = os_access.list_total_cpu_usage(1, 10)
        average_total_cpu = sum(usages) / len(usages)
        assert math.isclose(average_total_cpu, 0.9, abs_tol=0.15)
        # For POSIX CPU load we sleep for (sample_count + 1)
        # Check that this behavior does not produce timeout error
        usages = os_access.list_total_cpu_usage(6, 3)
        average_total_cpu = sum(usages) / len(usages)
        assert math.isclose(average_total_cpu, 0.9, abs_tol=0.15)
    finally:
        os_access._stop_cpu_load()


def test_rm_nonexistent_ubuntu18(exit_stack):
    _test_rm_nonexistent('ubuntu18', exit_stack)


def test_rm_nonexistent_win11(exit_stack):
    _test_rm_nonexistent('win11', exit_stack)


def _test_rm_nonexistent(one_vm_type, exit_stack):
    artifacts_dir = get_run_dir()
    vm_pool = public_default_vm_pool(artifacts_dir)
    one_vm = exit_stack.enter_context(vm_pool.clean_vm(vm_types[one_vm_type]))
    one_vm.ensure_started(artifacts_dir)
    exit_stack.enter_context(one_vm.os_access.prepared_one_shot_vm(artifacts_dir))
    exit_stack.enter_context(one_vm.os_access.traffic_capture_collector(artifacts_dir))
    os_access = one_vm.os_access
    filename = "NONEXTSTENT.IRRELEVANT"
    file = os_access.tmp() / filename
    with assert_raises_with_message_re(FileNotFoundError, filename):
        file.unlink()


def test_rm_nonexistent_missing_ok_ubuntu18(exit_stack):
    _test_rm_nonexistent_missing_ok('ubuntu18', exit_stack)


def test_rm_nonexistent_missing_ok_win11(exit_stack):
    _test_rm_nonexistent_missing_ok('win11', exit_stack)


def test_rm_nonexistent_missing_ok_win2019(exit_stack):
    _test_rm_nonexistent_missing_ok('win2019', exit_stack)


def _test_rm_nonexistent_missing_ok(one_vm_type, exit_stack):
    artifacts_dir = get_run_dir()
    vm_pool = public_default_vm_pool(artifacts_dir)
    one_vm = exit_stack.enter_context(vm_pool.clean_vm(vm_types[one_vm_type]))
    one_vm.ensure_started(artifacts_dir)
    exit_stack.enter_context(one_vm.os_access.prepared_one_shot_vm(artifacts_dir))
    exit_stack.enter_context(one_vm.os_access.traffic_capture_collector(artifacts_dir))
    os_access = one_vm.os_access
    filename = "NONEXTSTENT.IRRELEVANT"
    file = os_access.tmp() / filename
    file.unlink(missing_ok=True)


def test_rm_existing_file_ubuntu18(exit_stack):
    _test_rm_existing_file('ubuntu18', exit_stack)


def test_rm_existing_file_win11(exit_stack):
    _test_rm_existing_file('win11', exit_stack)


def _test_rm_existing_file(one_vm_type, exit_stack):
    artifacts_dir = get_run_dir()
    vm_pool = public_default_vm_pool(artifacts_dir)
    one_vm = exit_stack.enter_context(vm_pool.clean_vm(vm_types[one_vm_type]))
    one_vm.ensure_started(artifacts_dir)
    exit_stack.enter_context(one_vm.os_access.prepared_one_shot_vm(artifacts_dir))
    exit_stack.enter_context(one_vm.os_access.traffic_capture_collector(artifacts_dir))
    os_access = one_vm.os_access
    file = os_access.tmp() / "EXISTING.IRRELEVANT"
    file.write_bytes(b"This data is irrelevant")
    file.unlink()
    assert not file.exists()


def test_read_nonexistent_ubuntu18(exit_stack):
    _test_read_nonexistent('ubuntu18', exit_stack)


def test_read_nonexistent_win11(exit_stack):
    _test_read_nonexistent('win11', exit_stack)


def _test_read_nonexistent(one_vm_type, exit_stack):
    artifacts_dir = get_run_dir()
    vm_pool = public_default_vm_pool(artifacts_dir)
    one_vm = exit_stack.enter_context(vm_pool.clean_vm(vm_types[one_vm_type]))
    one_vm.ensure_started(artifacts_dir)
    exit_stack.enter_context(one_vm.os_access.prepared_one_shot_vm(artifacts_dir))
    exit_stack.enter_context(one_vm.os_access.traffic_capture_collector(artifacts_dir))
    os_access = one_vm.os_access
    filename = "NONEXTSTENT.IRRELEVANT"
    file = os_access.tmp() / filename
    with assert_raises_with_message_re(FileNotFoundError, filename):
        file.read_text('utf-8')


def test_connect_invalid_hostname_linux():
    ssh_shell = Ssh(
        hostname='nonexisting',
        port=22,
        username='irrelevant',
        key=None,
        )
    with assert_raises_with_message_re(RuntimeError, '.*DNS.*nonexisting.*'):
        ssh_shell.run(['irrelevant'])


def test_connect_invalid_hostname_windows():
    winrm = WinRM(
        address='nonexisting',
        port=435,
        username='irrelevant',
        password='irrelevant',
        )
    with assert_raises_with_message_re(RuntimeError, '.*DNS.*nonexisting.*'):
        WinRMShell(winrm)


def test_get_pid_by_name_win11(exit_stack):
    _test_get_pid_by_name('win11', exit_stack)


def test_get_pid_by_name_ubuntu18(exit_stack):
    _test_get_pid_by_name('ubuntu18', exit_stack)


def _test_get_pid_by_name(one_vm_type, exit_stack):
    artifacts_dir = get_run_dir()
    vm_pool = public_default_vm_pool(artifacts_dir)
    one_vm = exit_stack.enter_context(vm_pool.clean_vm(vm_types[one_vm_type]))
    one_vm.ensure_started(artifacts_dir)
    exit_stack.enter_context(one_vm.os_access.prepared_one_shot_vm(artifacts_dir))
    exit_stack.enter_context(one_vm.os_access.traffic_capture_collector(artifacts_dir))
    if one_vm_type.startswith('win'):
        process_name = 'tasklist'
    elif one_vm_type.startswith('ubuntu'):
        process_name = 'ps'
    else:
        raise RuntimeError(f'Unknown one_vm_type: {one_vm_type}')
    assert one_vm.os_access.get_pid_by_name(process_name)
