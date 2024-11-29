# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

_logger = logging.getLogger(__name__)


def connect_from_command_line(address, port, username, password):
    return [f'--auth=http://{username}:{password}@{address}:{port}']


def open_layout_from_command_line(layout_name):
    return [f'--layout-name={layout_name}']
