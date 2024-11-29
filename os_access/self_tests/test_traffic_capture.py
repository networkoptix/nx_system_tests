# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time

from directories import get_run_dir
from os_access import OsAccess
from vm.default_vm_pool import public_default_vm_pool
from vm.default_vm_pool import vm_types


def test_capture_file_exists_ubuntu18():
    _test_capture_file_exists('ubuntu18')


def test_capture_file_exists_win11():
    _test_capture_file_exists('win11')


def _test_capture_file_exists(one_vm_type):
    artifacts_dir = get_run_dir()
    vm_pool = public_default_vm_pool(artifacts_dir)
    with vm_pool.clean_vm(vm_types[one_vm_type]) as vm:
        vm.os_access.wait_ready()
        with vm.os_access.prepared_one_shot_vm(artifacts_dir):
            os_access = vm.os_access
            assert isinstance(os_access, OsAccess)
            with os_access.traffic_capture_collector(artifacts_dir):
                time.sleep(2)  # TODO: Check the .cap repeatedly.

        [cap_file] = artifacts_dir.glob('*.cap')
        assert cap_file.exists()
