# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Mapping
from typing import Sequence
from typing import Union
from urllib.error import URLError
from urllib.request import Request
from urllib.request import urlopen


def list_services(command_proxy_urls: Sequence[str]) -> Sequence[Union[Sequence[Mapping[str, str]], 'CommandProxyError']]:
    with ThreadPoolExecutor(max_workers=len(command_proxy_urls)) as executor:
        futures = []
        for url in command_proxy_urls:
            futures.append(executor.submit(_list_services, url))
        result = []
        for future in futures:
            try:
                result.append(future.result())
            except CommandProxyError as e:
                result.append(e)
        return result


def _list_services(command_proxy_url: str) -> Sequence[Mapping[str, str]]:
    user_units = _run_command(
        command_proxy_url,
        'systemctl --user list-units --type=service --type=timer --type=target --output=json',
        )
    user_units = json.loads(user_units)
    user_units = [service['unit'] for service in user_units if service['unit'] not in _system_units]
    user_units = ' '.join(user_units)
    units_data = _run_command(
        command_proxy_url,
        f'systemctl --user show {user_units} --no-pager --timestamp=utc',
        )
    result = []
    for unit_data in units_data.split(b'\n\n'):
        parsed_unit = _parse_unit_show_output(unit_data)
        result.append({
            'health': _unit_health(
                parsed_unit.get('SubState', ''), parsed_unit.get('ExecMainStatus', '')),
            'upheld_by': _unit_upheld_by(parsed_unit['Id'], parsed_unit.get('Before', '')),
            **parsed_unit,
            })
    return result


def _run_command(command_proxy_url: str, command: str) -> bytes:
    data = command.encode('utf8')
    request = Request(
        command_proxy_url,
        method='POST',
        data=data,
        headers={'Content-Length': str(len(data)), 'Content-Type': 'text/plain'},
        )
    try:
        with urlopen(request, timeout=5) as response:
            return response.read()
    except URLError as e:
        _logger.info(e)
        raise CommandProxyError(f"{e.__class__.__name__}: {e}")


def _parse_unit_show_output(systemd_show_output: bytes) -> Mapping[str, str]:
    result = {}
    for line in systemd_show_output.decode('utf8').splitlines():
        [key, _, value] = line.partition('=')
        result[key] = value
    return result


def _unit_health(sub_state: str, exec_main_status: str) -> str:
    if sub_state in ('active', 'running', 'waiting'):
        result = 'healthy'
    else:
        if int(exec_main_status) == 0:
            result = 'healthy'
        else:
            result = 'non-healthy'
    return result


def _unit_upheld_by(unit_id: str, before: str) -> str:
    parsed_before = before.split()
    [prefix, _, _] = unit_id.partition('@')
    for unit in parsed_before:
        if unit.startswith(prefix):
            result = unit
            break
    else:
        result = ''
    return result


class CommandProxyError(Exception):
    pass


_system_units = [
    'basic.target',
    'default.target',
    'paths.target',
    'sockets.target',
    'timers.target',
    'dbus.service',
    ]
_logger = logging.getLogger(__name__)
