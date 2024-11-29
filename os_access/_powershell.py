# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import base64
import json
import logging
from pathlib import PurePath
from textwrap import dedent

_logger = logging.getLogger(__name__)


def extract_script_from_command_line(command_line: str):
    tokens = [token for token in command_line.split(' ') if token]
    [*_, encoded_script] = tokens
    return base64.b64decode(encoded_script.encode('ascii')).decode('utf_16_le')


def start_raw_powershell_script(shell, script):
    _logger.debug("Run\n%s", script)
    return shell.Popen([
        'PowerShell',
        '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Unrestricted',
        '-EncodedCommand', base64.b64encode(script.encode('utf_16_le')).decode('ascii'),
        ])


class PowershellError(Exception):

    def __init__(self, type_name, category, message):
        super(PowershellError, self).__init__('{}: {}'.format(type_name, message))
        self.type_name = type_name
        self.category = category
        self.message = message


class PowerShellCommunicationError(Exception):
    pass


# TODO: Rename to power_shell.
def start_powershell_script(shell, script, variables):
    return start_raw_powershell_script(shell, power_shell_augment_script(script, variables))


def run_powershell_script(shell, script, variables, timeout_sec=None):
    run = start_raw_powershell_script(
        shell,
        power_shell_augment_script(script, variables),
        )
    with run:
        if timeout_sec is None:
            [stdout, stderr] = run.communicate()
        else:
            [stdout, stderr] = run.communicate(timeout_sec=timeout_sec)
        if not stdout:
            raise PowerShellCommunicationError(
                "Empty stdout; "
                "PowerShell couldn't run (system degradation? no memory?); "
                "stderr:\n"
                + stderr.decode(errors='replace'))
        try:
            outcome, data = json.loads(stdout.decode())
        except ValueError as e:
            raise PowerShellCommunicationError("Cannot decode STDOUT: {}".format(e))
        if outcome == 'success':
            return data
        raise PowershellError(*data)


def power_shell_augment_script(body, variables):
    parameters = []
    arguments = []
    for name, value in sorted(variables.items()):
        parameters.append('${name}'.format(name=name))
        if isinstance(value, PurePath):
            value = str(PurePath)
        arguments.append(
            "-{name}:(ConvertFrom-Json '{value}')".format(
                name=name,
                value=json.dumps(value, indent=4).replace("'", "''"),
                ),
            )
    function_name = 'Execute-Script'
    # Stub but valid PowerShell script. PyCharm syntax highlight can be enabled.
    # language=PowerShell
    script = '''
        $ProgressPreference = 'SilentlyContinue'
        $ErrorActionPreference = 'Stop'
        function Do-Something <# Function name #> (<# Parameters #>) {
            <# Body #>
        }
        try {
            $Result = Do-Something <# Execution #>
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
        '''
    script = dedent(script).strip()
    script = script.replace('Do-Something <# Function name #>', function_name)
    script = script.replace('<# Parameters #>', ', '.join(parameters))
    script = script.replace('Do-Something <# Execution #>', _indent(
        ' `\n'.join([function_name] + arguments)
        if arguments else
        function_name,
        ' ' * 8))
    script = script.replace('<# Body #>', _indent(
        dedent(body).strip(),
        ' ' * 4))
    script = script.replace(' \n', '\n')

    return script


def _indent(string, spaces='    '):
    return string.replace('\n', '\n' + spaces)
