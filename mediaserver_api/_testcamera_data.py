# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from urllib.parse import urlparse
from uuid import UUID


class Testcamera:

    def __init__(self, camera_id: UUID, raw):
        self._raw = raw
        self._id: UUID = camera_id

    @property
    def id(self) -> UUID:
        return self._id

    @property
    def physical_id(self) -> str:
        return self._raw['physicalId']

    @property
    def name(self) -> str:
        return self._raw['name']

    @property
    def address(self) -> str:
        url: str = self._raw['url']
        parsed = urlparse(url)
        return parsed.hostname


def testcamera_raw_input(index, address, server_id):
    mac = _mac(index)
    physical_id = mac
    raw = {
        'mac': mac,
        'physicalId': physical_id,
        'parentId': server_id,
        'typeId': '{f9c03047-72f1-4c04-a929-8538343b6642}',  # NetworkOptix Test Camera
        'url': f'tcp://{address}:4985/' + mac,
        'vendor': 'NetworkOptix',
        'name': f'TestCamera-{index:02d}',
        }
    return raw


def _mac(index):
    # Generate last 3 bytes of mac address
    mac_ei = '-'.join([
        '{:02x}'.format(index >> octet * 8 & 0xff)
        for octet in [2, 1, 0]])
    # Test Cameras mac addresses start with 92-61-00-00-01
    mac = '92-61-00-' + mac_ei
    return mac
