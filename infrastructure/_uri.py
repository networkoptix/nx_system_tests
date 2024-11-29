# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import inspect
import os
import socket
from pathlib import PurePath


def get_group_uri() -> str:
    """Get group name.

    If process is launched by systemd service - use corresponding environment variables
    for persistency.
    """
    try:
        unit_name = os.environ['FT_UNIT_NAME']
    except KeyError:
        group_name = f'//{socket.gethostname()}'
    else:
        [common_unit_name, _, _unit_params] = unit_name.partition('@')
        group_name = f'//{common_unit_name}'
    return group_name


def get_process_uri() -> str:
    """Get process URI that is unique across worker machines.

    If process is launched by systemd service - use corresponding environment variables
    for persistency.
    """
    group_uri = get_group_uri().rstrip('/')
    try:
        unit_name = os.environ['FT_UNIT_NAME']
    except KeyError:
        caller_frame_info = inspect.stack()[1]
        [_, caller_file_name, *_] = caller_frame_info
        caller_file = PurePath(caller_file_name)
        if caller_file.name == '__main__.py':
            caller_name = caller_file.parent.name
        else:
            caller_name = caller_file.stem
        process_uri = group_uri + f'/{caller_name}'
    else:
        process_uri = group_uri + f'/{socket.gethostname()}/{unit_name}'
    return process_uri


if __name__ == '__main__':
    os.environ.pop('FT_UNIT_NAME', None)
    print("FT_UNIT_NAME is absent")
    print(f'    Group URI: {get_group_uri()}')
    print(f'    Process URI: {get_process_uri()}')
    unit_without_params = 'simple_unit'
    os.environ['FT_UNIT_NAME'] = unit_without_params
    print(f"FT_UNIT_NAME is {unit_without_params}")
    print(f'    Group URI: {get_group_uri()}')
    print(f'    Process URI: {get_process_uri()}')
    unit_with_params = 'param_unit@001'
    os.environ['FT_UNIT_NAME'] = unit_with_params
    print(f"FT_UNIT_NAME is {unit_with_params}")
    print(f'    Group URI: {get_group_uri()}')
    print(f'    Process URI: {get_process_uri()}')
