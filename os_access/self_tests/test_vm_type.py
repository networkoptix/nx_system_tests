# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from vm.default_vm_pool import public_default_vm_pool
from vm.default_vm_pool import vm_types


def test_allocate():
    artifacts_dir = get_run_dir()
    vm_pool = public_default_vm_pool(artifacts_dir)
    with vm_pool.clean_vm(vm_types['ubuntu18']) as vm:
        assert vm.os_access.is_ready()


def test_allocate_two():
    artifacts_dir = get_run_dir()
    vm_pool = public_default_vm_pool(artifacts_dir)
    with vm_pool.clean_vm(vm_types['ubuntu18']) as a:
        with vm_pool.clean_vm(vm_types['ubuntu18']) as b:
            assert a.vm_control.name != b.vm_control.name
