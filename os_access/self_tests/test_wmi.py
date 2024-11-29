# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from os_access._windows_users import UserAccount
from os_access._windows_users import UserProfile
from os_access._winrm import BadSelectors
from os_access._winrm import Reference
from os_access.self_tests._windows_vm import windows_vm_running
from tests.infra import assert_raises

_logger = logging.getLogger(__name__)


def test_user_profiles(exit_stack):
    windows_vm = exit_stack.enter_context(windows_vm_running())
    winrm = windows_vm.os_access.winrm
    assert UserProfile(winrm, 'S-1-5-18').local_path


def test_get_user(exit_stack):
    windows_vm = exit_stack.enter_context(windows_vm_running())
    winrm = windows_vm.os_access.winrm
    domain = winrm.wsman_get('Win32_OperatingSystem', {})['CSName']
    account = UserAccount(winrm, domain + '\\Administrator')
    assert account.sid.as_str.endswith('-500')


def test_empty_enumeration_result(exit_stack):
    windows_vm = exit_stack.enter_context(windows_vm_running())
    winrm = windows_vm.os_access.winrm
    result = list(winrm.wsman_select('Win32_Service', {'Name': 'Non-Existent'}))
    assert not result


def test_all_of_base_class(exit_stack):
    windows_vm = exit_stack.enter_context(windows_vm_running())
    winrm = windows_vm.os_access.winrm
    result = list(winrm.wsman_all('wmi/Root/StandardCimV2/CIM_FilterEntryBase'))
    assert result
    cls_names = {ref.uri.split('/')[-1] for ref, _ in result}
    assert 'MSFT_NetProtocolPortFilter' in cls_names
    assert 'MSFT_NetApplicationFilter' in cls_names
    assert 'CIM_FilterEntryBase' not in cls_names


def test_selector_set_with_ref(exit_stack):
    windows_vm = exit_stack.enter_context(windows_vm_running())
    winrm = windows_vm.os_access.winrm
    [service_ref, _] = next(winrm.wsman_all('Win32_DependentService'))
    dependent_ref = service_ref.selectors['Dependent']
    antecedent_ref = service_ref.selectors['Antecedent']
    assert antecedent_ref.uri
    assert antecedent_ref.selectors
    antecedent_data = winrm.wsman_get(*antecedent_ref)
    assert antecedent_data
    rebuilt_service_ref = Reference('Win32_DependentService', {
        'Antecedent': antecedent_ref,
        'Dependent': dependent_ref,
        })
    rebuilt_service_ref_data = winrm.wsman_get(*rebuilt_service_ref)
    assert rebuilt_service_ref_data, "Manually created reference works"


def test_associations(exit_stack):
    windows_vm = exit_stack.enter_context(windows_vm_running())
    winrm = windows_vm.os_access.winrm
    assert list(winrm.wsman_associations(
        'Win32_Service', {'name': 'winrm'},
        association_cls_name='Win32_DependentService', source_field='Dependent',
        ))


def test_associations_by_base_class(exit_stack):
    windows_vm = exit_stack.enter_context(windows_vm_running())
    winrm = windows_vm.os_access.winrm
    rule_cls = 'wmi/Root/StandardCimV2/MSFT_NetFirewallRule'
    selectors = {
        'CreationClassName': 'MSFT|FW|FirewallRule|FPS-ICMP4-ERQ-In',
        'PolicyRuleName': '',
        'SystemCreationClassName': '',
        'SystemName': '',
        }
    result = list(winrm.wsman_associations(
        rule_cls, selectors,
        association_cls_name='MSFT_NetFirewallRuleFilters',
        ))
    cls_names = {ref.uri.split('/')[-1] for ref, _ in result}
    assert 'MSFT_NetFirewallRuleFilterByProtocolPort' in cls_names
    assert 'MSFT_NetFirewallRuleFilterByApplication' in cls_names
    assert 'MSFT_NetFirewallRuleFilters' not in cls_names


def test_associated(exit_stack):
    windows_vm = exit_stack.enter_context(windows_vm_running())
    winrm = windows_vm.os_access.winrm
    assert list(winrm.wsman_associated(
        'Win32_Service', {'name': 'winrm'},
        association_cls_name='Win32_DependentService',
        result_cls_name='Win32_Service',
        source_field='Dependent',
        destination_field='Antecedent',
        ))


def test_associated_by_base_class(exit_stack):
    windows_vm = exit_stack.enter_context(windows_vm_running())
    winrm = windows_vm.os_access.winrm
    rule_cls = 'wmi/Root/StandardCimV2/MSFT_NetFirewallRule'
    selectors = {
        'CreationClassName': 'MSFT|FW|FirewallRule|FPS-ICMP4-ERQ-In',
        'PolicyRuleName': '',
        'SystemCreationClassName': '',
        'SystemName': '',
        }
    result = list(winrm.wsman_associated(
        rule_cls, selectors,
        association_cls_name='MSFT_NetFirewallRuleFilters',
        result_cls_name='CIM_FilterEntryBase',
        ))
    cls_names = {ref.uri.split('/')[-1] for ref, _ in result}
    assert 'MSFT_NetProtocolPortFilter' in cls_names
    assert 'MSFT_NetApplicationFilter' in cls_names
    assert 'CIM_FilterEntryBase' not in cls_names


def test_wql_filter(exit_stack):
    windows_vm = exit_stack.enter_context(windows_vm_running())
    winrm = windows_vm.os_access.winrm
    query = '''
        select *
        from MSFT_NetFirewallRule
        where Enabled = 1 and DisplayName like "%remote%"
        '''
    result = list(winrm.wsman_wql('wmi/Root/StandardCimV2/*', query))
    assert result
    names = {item['DisplayName'] for _, item in result}
    assert 'Windows Remote Management (HTTP-In)' in names


def test_selector_set_filter(exit_stack):
    windows_vm = exit_stack.enter_context(windows_vm_running())
    winrm = windows_vm.os_access.winrm
    result = list(winrm.wsman_select('Win32_Service', {'State': 'Running', 'StartMode': 'Auto'}))
    assert result
    names = {item['Name'] for _, item in result}
    assert 'WinRM' in names  # How is it connected otherwise?


def test_invoke_with_empty_output(exit_stack):
    windows_vm = exit_stack.enter_context(windows_vm_running())
    winrm = windows_vm.os_access.winrm
    # This is rule on incoming ping requests. Should always be enabled anyway.
    rule_cls = 'wmi/Root/StandardCimV2/MSFT_NetFirewallRule'
    selectors = {
        'CreationClassName': 'MSFT|FW|FirewallRule|FPS-ICMP4-ERQ-In',
        'PolicyRuleName': '',
        'SystemCreationClassName': '',
        'SystemName': '',
        }
    assert winrm.wsman_invoke(rule_cls, selectors, 'Enable', {}) is None


def test_bad_selectors(exit_stack):
    windows_vm = exit_stack.enter_context(windows_vm_running())
    winrm = windows_vm.os_access.winrm
    rule_cls = 'wmi/Root/StandardCimV2/MSFT_NetFirewallRule'
    selectors = {'UNEXPECTED_SELECTOR_NAME': 'UNEXPECTED_SELECTOR_VALUE'}
    with assert_raises(BadSelectors):
        winrm.wsman_invoke(rule_cls, selectors, 'Enable', {})
