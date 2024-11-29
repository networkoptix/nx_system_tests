# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import VmsBenchmarkInstallation
from vm.default_vm_pool import public_default_vm_pool
from vm.default_vm_pool import vm_types

_logger = logging.getLogger(__name__)


def _test_vms_benchmark_installation(distrib_url, one_vm_type, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    artifacts_dir = get_run_dir()
    vm_pool = public_default_vm_pool(artifacts_dir)
    one_vm = exit_stack.enter_context(vm_pool.clean_vm(vm_types[one_vm_type]))
    one_vm.ensure_started(artifacts_dir)
    exit_stack.enter_context(one_vm.os_access.prepared_one_shot_vm(artifacts_dir))
    exit_stack.enter_context(one_vm.os_access.traffic_capture_collector(artifacts_dir))
    os_access = one_vm.os_access
    installer = installer_supplier.upload_benchmark(os_access)
    installation = VmsBenchmarkInstallation(os_access)
    installation.install(installer)
