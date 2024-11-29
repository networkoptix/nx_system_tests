# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from os_access._windows_registry import WindowsRegistry
from os_access.self_tests._windows_vm import windows_vm_running
from tests.infra import assert_raises


def test_list_empty_key(exit_stack):
    windows_vm = exit_stack.enter_context(windows_vm_running())
    windows_registry = WindowsRegistry(windows_vm.os_access.winrm)
    path = 'HKEY_LOCAL_MACHINE\\SOFTWARE'
    assert not windows_registry.list_values(path)


def test_list_values(exit_stack):
    windows_vm = exit_stack.enter_context(windows_vm_running())
    windows_registry = WindowsRegistry(windows_vm.os_access.winrm)
    path = 'HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion'
    assert windows_registry.list_values(path)


def test_list_keys(exit_stack):
    windows_vm = exit_stack.enter_context(windows_vm_running())
    windows_registry = WindowsRegistry(windows_vm.os_access.winrm)
    path = r'HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion'
    assert windows_registry.list_keys(path)


def test_list_single_value(exit_stack):
    windows_vm = exit_stack.enter_context(windows_vm_running())
    windows_registry = WindowsRegistry(windows_vm.os_access.winrm)
    key = r'HKEY_LOCAL_MACHINE\SOFTWARE\Network Optix Functional Tests\list_single_value'
    windows_registry.create_key(key)
    name = 'Dummy Value'
    windows_registry.set_dword(key, name, 1)
    [(returned_name, data_type)] = windows_registry.list_values(key)
    assert returned_name == name


def test_list_single_key(exit_stack):
    windows_vm = exit_stack.enter_context(windows_vm_running())
    windows_registry = WindowsRegistry(windows_vm.os_access.winrm)
    key = r'HKEY_LOCAL_MACHINE\SOFTWARE\Network Optix Functional Tests\list_single_key'
    windows_registry.create_key(key)
    name = 'Dummy Key'
    windows_registry.create_key(rf'{key}\{name}')
    [returned_name] = windows_registry.list_keys(key)
    assert returned_name == name


def test_create_set_get_delete(exit_stack):
    windows_vm = exit_stack.enter_context(windows_vm_running())
    windows_registry = WindowsRegistry(windows_vm.os_access.winrm)
    key = 'HKEY_LOCAL_MACHINE\\SOFTWARE\\Network Optix Functional Tests'
    windows_registry.create_key(key)
    name = 'Dummy Value'
    data = 'Dummy Data'
    windows_registry.set_string(key, name, data)
    assert windows_registry.get_string(key, name) == data


def test_delete_non_existing(exit_stack):
    windows_vm = exit_stack.enter_context(windows_vm_running())
    windows_registry = WindowsRegistry(windows_vm.os_access.winrm)
    nonexistent_key = 'HKEY_LOCAL_MACHINE\\SOFTWARE\\nonexistent_key'
    irrelevant_value = 'irrelevant_value'
    windows_registry.delete_value(nonexistent_key, irrelevant_value)


def test_dword_0(exit_stack):
    _test_dword(0, exit_stack)


def test_dword_1(exit_stack):
    _test_dword(1, exit_stack)


def test_dword_0x7FFFFFFF(exit_stack):
    _test_dword(0x7FFFFFFF, exit_stack)


def _test_dword(value, exit_stack):
    windows_vm = exit_stack.enter_context(windows_vm_running())
    windows_registry = WindowsRegistry(windows_vm.os_access.winrm)
    key = 'HKEY_LOCAL_MACHINE\\SOFTWARE\\Network Optix Functional Tests'
    windows_registry.create_key(key)
    name = 'DWORD Test'
    windows_registry.set_dword(key, name, value)
    assert windows_registry.get_dword(key, name) == value


def test_string_nonempty(exit_stack):
    _test_string('foo', exit_stack)


def test_string_empty(exit_stack):
    _test_string('', exit_stack)


def _test_string(value, exit_stack):
    windows_vm = exit_stack.enter_context(windows_vm_running())
    windows_registry = WindowsRegistry(windows_vm.os_access.winrm)
    key = 'HKEY_LOCAL_MACHINE\\SOFTWARE\\Network Optix Functional Tests'
    windows_registry.create_key(key)
    name = 'String Test'
    windows_registry.set_string(key, name, value)
    assert windows_registry.get_string(key, name) == value


def test_multi_string_multiple(exit_stack):
    _test_multi_string(['foo', 'bar'], exit_stack)


def test_multi_string_single(exit_stack):
    _test_multi_string(['foo'], exit_stack)


def test_multi_string_empty(exit_stack):
    _test_multi_string([], exit_stack)


def _test_multi_string(values, exit_stack):
    windows_vm = exit_stack.enter_context(windows_vm_running())
    windows_registry = WindowsRegistry(windows_vm.os_access.winrm)
    key = 'HKEY_LOCAL_MACHINE\\SOFTWARE\\Network Optix Functional Tests'
    windows_registry.create_key(key)
    name = 'MultiString Test'
    windows_registry.set_multi_string(key, name, values)
    assert windows_registry.get_multi_string(key, name) == values


def test_get_wrong_type(exit_stack):
    windows_vm = exit_stack.enter_context(windows_vm_running())
    windows_registry = WindowsRegistry(windows_vm.os_access.winrm)
    key = 'HKEY_LOCAL_MACHINE\\SOFTWARE\\Network Optix Functional Tests'
    windows_registry.create_key(key)
    windows_registry.set_dword(key, 'dword_value', 123)
    with assert_raises(TypeError):
        windows_registry.get_string(key, 'dword_value')
    windows_registry.set_string(key, 'string_value', 'qwe')
    with assert_raises(TypeError):
        windows_registry.get_dword(key, 'string_value')
