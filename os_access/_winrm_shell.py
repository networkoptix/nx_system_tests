# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from __future__ import annotations
from __future__ import annotations

import base64
import logging
import os
import subprocess
from pprint import pformat
from typing import Tuple

from os_access import Run
from os_access import Shell
from os_access._winrm import WinRMOperationTimeoutError
from os_access._winrm import WinRmHttpResponseTimeout
from os_access._winrm import _OptionSet
from os_access._winrm import _xml_aliases


class WinRMShell(Shell):

    def __init__(
            self,
            winrm,
            working_directory=None,
            env_vars=None,
            codepage=65001,  # UTF-8.
            idle_timeout=None,
            ):
        self._winrm = winrm
        self._shell_id, self.client_ip = self._open(
            working_directory, env_vars, codepage, idle_timeout)

    def close(self):
        try:
            self._winrm.act(
                class_uri='http://schemas.microsoft.com/wbem/wsman/1/windows/shell/cmd',
                action='http://schemas.xmlsoap.org/ws/2004/09/transfer/Delete',
                body={},
                selectors={'ShellId': self._shell_id},
                )
        except ConnectionError:
            _logger.info("WinRM session is already closed")

    def _open(self, working_directory, env_vars, codepage, idle_timeout) -> Tuple[str, str]:
        shell = {
            'rsp:InputStreams': 'stdin',
            'rsp:OutputStreams': 'stdout stderr',
            }
        if working_directory:
            # TODO ensure that rsp:WorkingDirectory should be nested within rsp:Shell  # NOQA
            shell['rsp:WorkingDirectory'] = working_directory
        # TODO make it so the input is given in milliseconds and converted to xs:duration  # NOQA
        if idle_timeout:
            shell['rsp:IdleTimeOut'] = idle_timeout
        if env_vars:
            # the rsp:Variable tag needs to be list of variables so that all
            # environment variables in the env_vars dict are set on the shell
            env = []
            for key, value in env_vars.items():
                env.append({'@Name': key, '#text': value})
            shell['rsp:Environment'] = {'rsp:Variable', env}
        body = {'rsp:Shell': shell}
        response = self._winrm.act(
            class_uri='http://schemas.microsoft.com/wbem/wsman/1/windows/shell/cmd',
            action='http://schemas.xmlsoap.org/ws/2004/09/transfer/Create',
            body=body,
            selectors={},
            options=_OptionSet.from_dict({'WINRS_NOPROFILE': 'FALSE', 'WINRS_CODEPAGE': str(codepage)}),
            )
        shell_id = response['rsp:Shell']['rsp:ShellId']
        client_ip = response['rsp:Shell']['rsp:ClientIP']
        return shell_id, client_ip

    def invoke_method(self, method, body, timeout_sec=None):
        return self._winrm.act(
            class_uri='http://schemas.microsoft.com/wbem/wsman/1/windows/shell/cmd',
            action=f'http://schemas.microsoft.com/wbem/wsman/1/windows/shell/{method}',
            body=body,
            selectors={'ShellId': self._shell_id},
            timeout_sec=timeout_sec,
            )

    def Popen(self, args, **kwargs):
        if kwargs:
            raise ValueError(
                f"Working directory and environment variables can be provided "
                f"when creating a shell: {kwargs}")
        return _WinRMRun(self, args)

    @staticmethod
    def args_to_command_line(args):
        if isinstance(args, str):
            if '\n' in args:
                raise ValueError(
                    "Newlines are not supported by WinRM shell; "
                    f"it's unknown how to implement this: {args!r}")
            return args
        args_as_str_list = []
        for arg in args:
            if isinstance(arg, str):
                if '\n' in arg:
                    raise ValueError(
                        "Newlines are not supported by WinRM shell; "
                        f"it's unknown how to implement this: {arg!r}")
                args_as_str_list.append(arg)
            elif isinstance(arg, os.PathLike):
                args_as_str_list.append(os.fspath(arg))
            elif isinstance(arg, int):
                args_as_str_list.append(str(arg))
            else:
                raise TypeError("Unsupported arg type: {!r}".format(arg))
        return subprocess.list2cmdline(args_as_str_list)


class _WinRMRun(Run):

    def __init__(self, shell, args):
        super().__init__(args)

        # Rewrite with bigger MaxEnvelopeSize, currently hardcoded to 150k, while 8M needed.
        self._shell = shell

        # `WINRS_SKIP_CMD_SHELL` and `WINRS_CONSOLEMODE_STDIN` don't work.
        # See: https://social.msdn.microsoft.com/Forums/azure/en-US/d089b9b6-f7d3-439f-94f3-6e75497d113a  # noqa
        # Commands are executed with `cmd /c`.
        # `cmd /c` has its own special (but simple) quoting rules. Thoroughly read output of `cmd /?`.
        # In short, quote normally, and then simply put quotes around.
        args = self._shell.args_to_command_line(args)
        _logger.info("Command: %s", args)
        body = {
            'rsp:CommandLine': {
                'rsp:Command': '"' + args + '"',
                },
            }
        response = self._shell.invoke_method(
            method='Command',
            body=body,
            )
        self._command_id = response['rsp:CommandResponse']['rsp:CommandId']
        # TODO: Prohibit writes when passing up.
        self._returncode = None

    def wait(self, timeout=None):
        self.communicate() if timeout is None else self.communicate(timeout_sec=timeout)
        return self._returncode

    def send(self, stdin_bytes, is_last=False):
        # See: https://msdn.microsoft.com/en-us/library/cc251742.aspx
        stream = {
            '@Name': 'stdin',
            '@CommandId': self._command_id,
            # TODO: Chunked stdin upload.
            '#text': base64.b64encode(stdin_bytes),
            }
        if is_last:
            stream['@End'] = 'true'
        body = {'rsp:Send': {'rsp:Stream': stream}}
        self._shell.invoke_method(
            method='Send',
            body=body,
            )
        sent_bytes = len(stdin_bytes)
        return sent_bytes

    @property
    def returncode(self):
        return self._returncode

    @staticmethod
    def _parse_std_streams(response):
        # Stream tags absent if streams are closed but process still runs.
        nodes = response['rsp:ReceiveResponse'].get('rsp:Stream', [])
        stdout = stderr = b''
        for node in nodes:
            if not node.get('#text'):
                continue
            if node['@Name'] == 'stdout':
                stdout += base64.b64decode(node['#text'])
            elif node['@Name'] == 'stderr':
                stderr += base64.b64decode(node['#text'])
        assert isinstance(stdout, bytes)
        assert isinstance(stderr, bytes)
        return stdout, stderr

    @staticmethod
    def _parse_command_state(response):
        node = response['rsp:ReceiveResponse']['rsp:CommandState']
        state = node['@State']
        if state == _xml_aliases['rsp'] + '/CommandState/Done':
            return int(node['rsp:ExitCode'])
        if state == _xml_aliases['rsp'] + '/CommandState/Pending':
            return None
        if state == _xml_aliases['rsp'] + '/CommandState/Running':
            if 'rsp:ExitCode' in node:
                raise RuntimeError(f"Running command with exit code: {node}")
            return None
        raise RuntimeError(f"Command with unexpected state: {node}")

    def receive(self, timeout_sec):
        # TODO: Support timeouts.
        if self._returncode is not None:
            # TODO: What if process is done but streams are not closed? Is that possible?
            return None, None
        # noinspection PyProtectedMember
        try:
            body = {
                'rsp:Receive': {
                    'rsp:DesiredStream': {
                        '@CommandId': self._command_id,
                        '#text': 'stdout stderr',
                        },
                    },
                }
            response = self._shell.invoke_method(
                method='Receive',
                body=body,
                timeout_sec=timeout_sec,
                )
        except (WinRMOperationTimeoutError, WinRmHttpResponseTimeout):
            # OperationTimeout - no output during the timeout period.
            # The caller takes empty chunks and can try to receive again.
            return b'', b''
        self._returncode = self._parse_command_state(response)
        return self._parse_std_streams(response)

    def _send_signal(self, sig):
        """Send ctrl_c, ctrl_break or terminate.

        Signals: https://docs.microsoft.com/en-us/windows/console/ctrl-c-and-ctrl-break-signals.
        WSMV signal codes: https://msdn.microsoft.com/en-us/library/cc761132.aspx.
        WSMV example: https://msdn.microsoft.com/en-us/library/cc251743.aspx.
        """
        code = 'http://schemas.microsoft.com/wbem/wsman/1/windows/shell/signal/' + sig
        body = {
            'rsp:Signal': {
                '@CommandId': self._command_id,
                'rsp:Code': code,
                },
            }
        response = self._shell.invoke_method(
            method='Signal',
            body=body,
            )
        _logger.debug("Terminate response:\n%s", pformat(response))

    def terminate(self):
        self._send_signal('ctrl_c')

    def kill(self):
        self._send_signal('ctrl_break')

    def close(self):
        self._send_signal('terminate')


_logger = logging.getLogger(__name__)
