# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import base64
import random
import re
import string
from datetime import datetime
from itertools import count
from typing import Collection
from typing import Mapping
from typing import Sequence
from typing import Tuple
from typing import Union

from doubles.licensing.local_license_server._signature import sign


def generate_license(license_data: Mapping[str, Union[str, float]]) -> Tuple[str, str]:
    data = {
        'NAME': 'Auto Test',
        'COMPANY2': 'Network Optix',
        'ORDERTYPE': 'purchase',
        'ORDERID2': 'TEST-SB',
        'AUTHORIZEDBY': '1',
        'BRAND2': 'hdwitness',
        'CLASS2': 'digital',
        'TRIALDAYS2': 0,
        'NUMPACKS': 1,
        'QUANTITY2': 1,
        'REPLACEMENT[]': [],
        'FIXED_EXPIRATION_TS': '',
        **license_data,
        }
    data['QUANTITY2'] = int(data['QUANTITY2'])
    [key, serial] = _generate_key_and_serial(data['CLASS2'], data['QUANTITY2'])
    _licenses[key] = {
        'hwids': [],
        'is_enabled': True,
        'deactivation_count': 0,
        'license_data': data,
        }
    return key, serial


def activate_license(
        key: str,
        vms_version: str,
        hwids: Mapping[str, Union[str, Collection[str]]],
        ) -> str:
    if key not in _licenses:
        raise _KeyNotExist(key)
    parsed_hwids = []
    hwid_re = re.compile(r'hwid(?P<version>\d*)\[\]')
    for hwid_name, hwid_values in hwids.items():
        version_match = hwid_re.match(hwid_name).group('version')
        version = int(version_match) if version_match else 0
        if isinstance(hwid_values, str):
            hwid_values = [hwid_values]
        parsed_hwids.append((version, hwid_values[::-1]))
    sorted_hwids = [
        hwid
        for _version, hwid_values in sorted(parsed_hwids, key=lambda x: x[0])
        for hwid in hwid_values]
    _licenses[key].setdefault('hwids', []).extend(sorted_hwids)
    _licenses[key]['is_enabled'] = True
    license_data = _licenses[key]['license_data']
    serialized = ''
    serialized += f'NAME={license_data["BRAND2"]}\n'
    serialized += f'SERIAL={key}\n'
    serialized += f'HWID={sorted_hwids[-1]}\n'
    serialized += f'COUNT={license_data["QUANTITY2"]}\n'
    serialized += f'CLASS={license_data["CLASS2"]}\n'
    serialized += f'VERSION={vms_version}\n'
    serialized += f'BRAND={license_data["BRAND2"]}\n'
    serialized += f'EXPIRATION={_format_expiration_date(license_data["FIXED_EXPIRATION_TS"])}\n'
    signature = sign('vms.nop.pvt', serialized.encode('ascii'))
    encoded_signature = base64.b64encode(signature)
    serialized += f'SIGNATURE2={encoded_signature.decode("ascii")}\n'
    if 'COMPANY2' in license_data:
        serialized += f'COMPANY={license_data["COMPANY2"]}\n'
    serialized += 'SUPPORT=rbarsegian@networkoptix.com\n'
    serialized += f'DEACTIVATIONS={_licenses[key]["deactivation_count"]}\n'
    serialized += "CLOUDSYSTEMID=\n"
    serialized += "CLOUDSTORAGEBYTES=0\n"
    return serialized


def validate_license(vms_version: str, keys: Collection[str]):
    result = {'status': 'ok', 'licenses': [], 'licenseErrors': {}}
    for key in keys:
        if key not in _licenses or not _licenses[key]['is_enabled']:
            result['licenseErrors'][key] = {'code': 'InvalidKey', 'text': 'InvalidKey'}
            continue
        if _licenses[key]['is_enabled'] and not _licenses[key]['hwids']:
            result['licenseErrors'][key] = {'code': 'NotActivated', 'text': 'NotActivated'}
            continue
        license_data = _licenses[key]['license_data']
        hwids = _licenses[key]["hwids"]
        serialized = ''
        serialized += f'NAME={license_data["BRAND2"]}\n'
        serialized += f'SERIAL={key}\n'
        serialized += f'HWID={hwids[-1]}\n' if hwids else ''
        serialized += f'COUNT={license_data["QUANTITY2"]}\n'
        serialized += f'CLASS={license_data["CLASS2"]}\n'
        serialized += f'VERSION={vms_version}\n'
        serialized += f'BRAND={license_data["BRAND2"]}\n'
        serialized += f'EXPIRATION={_format_expiration_date(license_data["FIXED_EXPIRATION_TS"])}\n'
        signature = sign('vms.nop.pvt', serialized.encode('ascii'))
        encoded_signature = base64.b64encode(signature)
        license_response_data = {
            'name': license_data["BRAND2"],
            'key': key,
            'hardwareId': _licenses[key]["hwids"][-1],
            'cameraCount': license_data["QUANTITY2"],
            'licenseType': license_data["CLASS2"],
            'version': vms_version,
            'brand': license_data["BRAND2"],
            'expiration': _format_expiration_date(license_data["FIXED_EXPIRATION_TS"]),
            'signature': encoded_signature.decode("ascii"),
            }
        if 'COMPANY2' in license_data:
            license_response_data['company'] = license_data['COMPANY2']
        license_response_data['support'] = 'rbarsegian@networkoptix.com'
        license_response_data['cloudSystemId'] = ''
        license_response_data['cloudStorageBytes'] = 0
        license_response_data['deactivations'] = _licenses[key]['deactivation_count']
        result['licenses'].append(license_response_data)
    return result


def deactivate_license(key: str):
    if key not in _licenses:
        raise _KeyNotExist(key)
    if not _licenses[key]['is_enabled'] or not _licenses[key]['hwids']:
        raise _AlreadyDeactivated(key)
    _licenses[key]['hwids'] = []
    _licenses[key]['is_enabled'] = False
    _licenses[key]['deactivation_count'] += 1


def disable_license(key: str):
    _licenses.setdefault(key, {})['hwids'] = []
    _licenses[key]['is_enabled'] = False


def get_license(key: str) -> Mapping[str, Union[bool, Sequence[str]]]:
    return _licenses.setdefault(key, {'hwids': [], 'is_enabled': False})


def _generate_key_and_serial(license_type: str, license_count: int) -> Tuple[str, str]:
    chars = string.ascii_uppercase + string.digits[1:]
    key = '-'.join(
        ''.join(random.sample(chars, 4))
        for _ in range(4)
        )
    if license_type == 'digital':
        prefix = '01'
    elif license_type == 'analog':
        prefix = '02'
    elif license_type == 'edge':
        prefix = '03'
    elif license_type == 'vmax':
        prefix = '04'
    elif license_type == 'videowall':
        prefix = '05'
    elif license_type == 'analogencoder':
        prefix = '06'
    elif license_type == 'starter':
        prefix = '07'
    elif license_type == 'iomodule':
        prefix = '08'
    elif license_type == 'bridge':
        prefix = '09'
    elif license_type == 'nvr':
        prefix = '10'
    elif license_type == 'trial':
        prefix = '00'
    else:
        raise RuntimeError(f"Unknown license type {license_type}")
    date = datetime.utcnow().strftime('%d%m%y')
    license_id = next(_license_id)  # Single test will never exceed 100000 licenses
    serial = f'{prefix}-{license_count:04}-{date}-{license_id:05}'
    return key, serial


def _format_expiration_date(fixed_expiration_ts: str) -> str:
    if not fixed_expiration_ts:
        return ''
    expiration_date = datetime.strptime(fixed_expiration_ts, '%m/%d/%Y')
    return expiration_date.strftime('%Y-%m-%d %H:%M:%S')


class _KeyNotExist(Exception):
    pass


class _AlreadyDeactivated(Exception):
    pass


_license_id = count(1)
_licenses = {}
