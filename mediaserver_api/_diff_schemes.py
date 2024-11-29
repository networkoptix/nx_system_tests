# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import argparse
import json
import logging
from pathlib import Path

from mediaserver_api._data_differ import DataDiffer
from mediaserver_api._data_differ import KeyInfo
from mediaserver_api._data_differ import PathPattern
from mediaserver_api._data_differ import log_diff_list

_logger = logging.getLogger(__name__)

DEFAULT_FULL_INFO_DIFF_WHITE_LIST = [
    PathPattern('cameras/**'),
    PathPattern('cameraUserAttributesList/**'),
    PathPattern('servers/**'),
    PathPattern('serversUserAttributesList/**'),
    PathPattern('users/**'),
    PathPattern('videowalls/**'),
    ]

_server_key_info = KeyInfo('server', ['id'], ['name'])
_user_key_info = KeyInfo('user', ['id'], ['name'])
_storage_key_info = KeyInfo('storage', ['id'], ['name'])
_camera_key_info = KeyInfo('camera', ['id'], ['name'])
_property_key_info = KeyInfo('property', ['resourceId', 'name'], ['resourceId', 'name'])

server_differ = DataDiffer('server', [(PathPattern(), _server_key_info)])
user_differ = DataDiffer('user', [(PathPattern(), _user_key_info)])
storage_differ = DataDiffer('storage', [(PathPattern(), _storage_key_info)])
camera_differ = DataDiffer('camera', [(PathPattern(), _camera_key_info)])
resource_params_differ = DataDiffer('resource_params', [(PathPattern(), _property_key_info)])

full_info_differ = DataDiffer('full-info', [
    (PathPattern('servers'), _server_key_info),
    (PathPattern('users'), _user_key_info),
    (PathPattern('storages'), _storage_key_info),
    (PathPattern('cameras'), _camera_key_info),
    (PathPattern('layouts'), KeyInfo('layout', ['id'], ['name'])),
    (PathPattern('layouts/*/items'), KeyInfo('layout_item', ['id'], ['id'])),
    (PathPattern('allProperties'), _property_key_info),
    (PathPattern('resStatusList'), KeyInfo('status', ['id'], ['id'])),
    (PathPattern('resourceTypes'), KeyInfo('resource_type', ['id'], ['name'])),
    (PathPattern('resourceTypes/*/propertyTypes'), KeyInfo('property_type', ['name'], ['name'])),
    (PathPattern('rules'), KeyInfo('rule', ['id'], ['id'])),
    (PathPattern('videowalls'), KeyInfo('videowall', ['id'], ['name'])),
    ])

raw_differ = DataDiffer('raw')

transaction_log_differ = DataDiffer('transaction-log', [
    (
        PathPattern(),
        KeyInfo(
            'transaction',
            ['tran.peerID', 'tran.persistentInfo.dbID', 'tran.persistentInfo.sequence'],
            ['tranGuid', 'tran.command'])),
    ])

# command-line interface for data differ:

_differ_map = {
    differ.name: differ for differ in [
        raw_differ,
        full_info_differ,
        transaction_log_differ,
        ]}


def _differ(value):
    differ = _differ_map.get(value)
    if not differ:
        raise argparse.ArgumentTypeError(
            '%r is not an known differ. Known are: %r' % (value, _differ_map.keys()))
    return differ


def _dict_file(value):
    path = Path(value).expanduser()
    if not path.is_file():
        raise argparse.ArgumentTypeError('%s is not an existing file' % path)
    with path.open() as f:
        return json.load(f)


def _differ_util():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'differ',
        type=_differ,
        help='Differ to use. One of %r' % _differ_map.keys(),
        )
    parser.add_argument('x', type=_dict_file, help='Path to first json file.')
    parser.add_argument('y', type=_dict_file, help='Path to second json file.')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose logging mode.')
    args = parser.parse_args()

    format = '%(asctime)-15s %(message)s'
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format=format)

    diff_list = args.differ.diff(args.x, args.y)
    _logger.info('Diff contains %d elements', len(diff_list))
    log_diff_list(_logger.info, diff_list)


if __name__ == '__main__':
    _differ_util()
