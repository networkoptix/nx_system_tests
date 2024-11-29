# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from typing import cast

from directories import get_run_dir
from long_tests.strace import strace
from os_access import PosixAccess
from vm.default_vm_pool import public_default_vm_pool
from vm.default_vm_pool import vm_types


def test_strace():
    artifacts_dir = get_run_dir()
    vm_pool = public_default_vm_pool(artifacts_dir)
    with vm_pool.clean_vm(vm_types['ubuntu22']) as vm:
        vm.ensure_started(artifacts_dir)
        with vm.os_access.prepared_one_shot_vm(artifacts_dir):
            pid = vm.os_access.get_pid_by_name('sftp-server')
            posix_access = cast(PosixAccess, vm.os_access)
            with strace(posix_access, pid) as strace_log_file:
                posix_access.path('/var/log/test.log').write_bytes(b'123')
            log_data = strace_log_file.read_text()
            assert '/var/log/test.log' in log_data
