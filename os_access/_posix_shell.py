# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import os
import shlex
from abc import ABCMeta
from abc import abstractmethod
from ipaddress import IPv4Address
from ipaddress import IPv6Address
from textwrap import dedent

from os_access._command import Shell

_PROHIBITED_ENV_NAMES = {'PATH', 'HOME', 'USER', 'SHELL', 'PWD', 'TERM'}


def quote_arg(arg):
    return shlex.quote(str(arg))


def command_to_script(command):
    str_args = []
    for arg in command:
        if isinstance(arg, str):
            str_args.append(arg)
        elif isinstance(arg, int) and not isinstance(arg, bool):
            str_args.append(str(arg))
        elif isinstance(arg, os.PathLike):
            str_args.append(os.fspath(arg))
        else:
            raise TypeError(f"Unsupported arg type {arg} in command {command}")
    return shlex.join(str_args)


def env_values_to_str(env):
    converted_env = {}
    for name, value in env.items():
        if isinstance(value, bool):  # Beware: bool is subclass of int.
            converted_env[name] = 'true' if value else 'false'
            continue
        if isinstance(value, (int, IPv6Address, IPv4Address)):
            converted_env[name] = str(value)
            continue
        if isinstance(value, os.PathLike):
            converted_env[name] = os.fspath(value)
            continue
        if isinstance(value, str):
            converted_env[name] = value
            continue
        if value is None:
            converted_env[name] = ''
            continue
        raise RuntimeError(f"Unexpected value {value!r} of type {type(value)}")
    return converted_env


def env_to_command(env):
    converted_env = env_values_to_str(env)
    command = []
    for name, value in converted_env.items():
        if name in _PROHIBITED_ENV_NAMES:
            raise ValueError(f"Potential name clash with built-in name: {name}")
        command.append(f'export {name}={quote_arg(str(value))}')
    return command


def augment_script(script, cwd=None, env=None, set_eux=True, shebang=False):
    augmented_script_lines = []
    if shebang:
        # language=Bash
        augmented_script_lines.append('#!/bin/sh')
    if set_eux:
        # language=Bash
        augmented_script_lines.append('set -eux')  # It's sh (dash), pipefail cannot be set here.
    if cwd is not None:
        augmented_script_lines.append(command_to_script(['cd', cwd]))
    if env is not None:
        augmented_script_lines.extend(env_to_command(env))
    augmented_script_lines.append(dedent(script).strip())
    augmented_script = '\n'.join(augmented_script_lines)
    return augmented_script


class PosixShell(Shell, metaclass=ABCMeta):
    """Posix-specific interface."""

    @abstractmethod
    def is_working(self) -> bool:
        pass

    @abstractmethod
    def close(self):
        pass
