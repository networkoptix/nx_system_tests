# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from contextlib import contextmanager

from directories import get_run_dir
from vm.default_vm_pool import public_default_vm_pool
from vm.default_vm_pool import vm_types


@contextmanager
def windows_vm_running():
    artifacts_dir = get_run_dir()
    vm_pool = public_default_vm_pool(artifacts_dir)
    with vm_pool.clean_vm(vm_types['win11']) as windows_vm:
        windows_vm.os_access.wait_ready()
        with windows_vm.os_access.prepared_one_shot_vm(artifacts_dir):
            yield windows_vm
