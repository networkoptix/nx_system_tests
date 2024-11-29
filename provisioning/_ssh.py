# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import os
import shlex
import subprocess


def ssh(host: str, command: str, *, options=()):
    r = subprocess.run(
        _build(host, command, options),
        stdout=subprocess.PIPE,
        # It may hang waiting for input when no input is actually needed.
        # See: https://github.com/PowerShell/Win32-OpenSSH/issues/1334
        stdin=subprocess.DEVNULL,
        timeout=600,
        )
    if r.returncode == 255:
        raise SSHCannotConnect()
    r.check_returncode()
    return r


def ssh_still(host: str, command: str):
    r = subprocess.run(
        _build(host, command),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        # It may hang waiting for input when no input is actually needed.
        # See: https://github.com/PowerShell/Win32-OpenSSH/issues/1334
        stdin=subprocess.DEVNULL,
        timeout=600,
        )
    if r.returncode == 255:
        raise SSHCannotConnect(r.stderr.decode())
    return r


def ssh_write_file(host, user, dest, data):
    return ssh_input(host, f'sudo -u {user} dd status=none of={dest}', data)


def ssh_input(host: str, command: str, stdin: bytes):
    r = subprocess.run(_build(host, command), input=stdin, timeout=60)
    if r.returncode == 255:
        raise SSHCannotConnect()
    r.check_returncode()
    return r


def _build(host, command, options=()):
    # In BatchMode, execution fails if interactive input is required.
    full_command = ['ssh', '-oBatchMode=yes', *options, host, command]
    _log(full_command)
    return full_command


def scp(host: str, local: os.PathLike, remote: str = ''):
    command = ['scp', local, host + ':' + remote]
    _log(command)
    r = subprocess.run(command)
    if r.returncode == 255:
        raise SSHCannotConnect()
    r.check_returncode()


def _log(command):
    if os.name == 'nt':
        _logger.info("Run: %s", subprocess.list2cmdline(command))
    else:
        # shlex.join() only works with Iterable[str] and fails with PathLike
        command = [str(arg) if isinstance(arg, os.PathLike) else arg for arg in command]
        _logger.info("Run: %s", shlex.join(command))


class SSHCannotConnect(Exception):
    pass


_logger = logging.getLogger(__name__)
