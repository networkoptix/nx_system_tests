# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from os_access import OsAccess
from os_access import ServiceNotFoundError
from tests.infra import assert_raises
from tests.waiting import wait_for_truthy
from vm.default_vm_pool import public_default_vm_pool
from vm.default_vm_pool import vm_types


def test_stop_start_ubuntu18(exit_stack):
    _test_stop_start('ubuntu18', exit_stack)


def test_stop_start_win11(exit_stack):
    _test_stop_start('win11', exit_stack)


def _test_stop_start(one_vm_type, exit_stack):
    artifacts_dir = get_run_dir()
    vm_pool = public_default_vm_pool(artifacts_dir)
    one_vm = exit_stack.enter_context(vm_pool.clean_vm(vm_types[one_vm_type]))
    one_vm.ensure_started(artifacts_dir)
    exit_stack.enter_context(one_vm.os_access.prepared_one_shot_vm(artifacts_dir))
    exit_stack.enter_context(one_vm.os_access.traffic_capture_collector(artifacts_dir))
    service = one_vm.os_access.dummy_service()
    # Initial state can be either started or stopped.
    # Service should be in same state as it was before.
    # Both actions must be executed.
    if service.is_running():
        service.stop()
        wait_for_truthy(lambda: not service.is_running(), description="service is stopped")
        service.start()
        wait_for_truthy(service.is_running)
    else:
        service.start()
        wait_for_truthy(service.is_running)
        service.stop()
        wait_for_truthy(lambda: not service.is_running(), description="service is stopped")


def test_bad_service_definition_ubuntu18(exit_stack):
    _test_bad_service_definition('ubuntu18', exit_stack)


def test_bad_service_definition_win11(exit_stack):
    _test_bad_service_definition('win11', exit_stack)


def _test_bad_service_definition(one_vm_type, exit_stack):
    artifacts_dir = get_run_dir()
    vm_pool = public_default_vm_pool(artifacts_dir)
    one_vm = exit_stack.enter_context(vm_pool.clean_vm(vm_types[one_vm_type]))
    one_vm.ensure_started(artifacts_dir)
    exit_stack.enter_context(one_vm.os_access.prepared_one_shot_vm(artifacts_dir))
    exit_stack.enter_context(one_vm.os_access.traffic_capture_collector(artifacts_dir))

    os_access: OsAccess = one_vm.os_access
    service_name = "there_is_some_service_which_must_not_exists"
    bad_service = os_access.service(service_name)

    with assert_raises(ServiceNotFoundError):
        bad_service.status()
