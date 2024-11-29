# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
import logging
from textwrap import dedent

from os_access import power_shell_augment_script
from os_access._powershell import PowershellError
from os_access._powershell import run_powershell_script
from os_access._powershell import start_raw_powershell_script
from os_access._winrm_shell import WinRMShell
from os_access.self_tests._windows_vm import windows_vm_running

_logger = logging.getLogger(__name__)


def test_start_script(exit_stack):
    windows_vm = exit_stack.enter_context(windows_vm_running())
    winrm_shell = WinRMShell(windows_vm.os_access.winrm)
    # language=PowerShell
    powershell_command = '''
        $x = 1111
        $y = $x * $x
        $y | ConvertTo-Json
        '''
    run = start_raw_powershell_script(winrm_shell, powershell_command)
    stdout, stderr = run.communicate()
    assert json.loads(stdout.decode()) == 1234321


def test_format_script():
    # Variable names are sorted to get predictable result.
    # language=PowerShell
    body = '''
        Do-This -Carefully $BThing
        Make-It -Real -Quality $AQuality
        '''
    variables = {'AQuality': 100, 'BThing': ['Something', 'Another']}
    # language=PowerShell
    expected_formatted_script = dedent('''
        $ProgressPreference = 'SilentlyContinue'
        $ErrorActionPreference = 'Stop'
        function Execute-Script ($AQuality, $BThing) {
            Do-This -Carefully $BThing
            Make-It -Real -Quality $AQuality
        }
        try {
            $Result = Execute-Script `
                -AQuality:(ConvertFrom-Json '100') `
                -BThing:(ConvertFrom-Json '[
                    "Something",
                    "Another"
                ]')
            # @( $Result ) converts $null to empty array, single object to array with single element
            # and don't make an array nested.
            ConvertTo-Json @( 'success', @( $Result ) )
        } catch {
            $ExceptionInfo = @(
                $_.Exception.GetType().FullName,
                $_.CategoryInfo.Category.ToString(),
                $_.Exception.Message
            )
            ConvertTo-Json @( 'fail', $ExceptionInfo )
        }
        ''').strip()
    assert power_shell_augment_script(body, variables) == expected_formatted_script


def test_run_script(exit_stack):
    windows_vm = exit_stack.enter_context(windows_vm_running())
    winrm_shell = WinRMShell(windows_vm.os_access.winrm)
    result = run_powershell_script(
        winrm_shell,
        # language=PowerShell
        '''
            $a = $x * $x
            $b = $a + $y
            return $b
            ''',
        {'x': 2, 'y': 5})
    assert result == [9]


def test_run_script_error(exit_stack):
    windows_vm = exit_stack.enter_context(windows_vm_running())
    winrm_shell = WinRMShell(windows_vm.os_access.winrm)
    nonexistent_group = 'nonexistentGroup'
    try:
        _ = run_powershell_script(
            winrm_shell,
            # language=PowerShell
            '''Get-LocalGroup -Name:$Group''',
            {'Group': nonexistent_group})
    except PowershellError as e:
        assert e.message == 'Group nonexistentGroup was not found.'
        assert e.category == 'ObjectNotFound'
    else:
        raise Exception("Did not raise")
