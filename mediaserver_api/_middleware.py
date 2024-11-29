# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
"""Check Mediaserver API reponse for passwords, keys and other secrets.

>>> check_response_for_credentials({'test': 1}, '/')
>>> check_response_for_credentials({'test': {'key': None}}, '/')
>>> check_response_for_credentials({'test': [{'token': ''}]}, '/')
>>> check_response_for_credentials({'test': 1, 'passwd': ''}, '/')
>>> check_response_for_credentials({'password': None}, '/')
>>> check_response_for_credentials({'a': [{'b': [{'token': ''}]}]}, '/')
>>> check_response_for_credentials({'authKey': '**************'}, '/')
>>> check_response_for_credentials({'passwd': '************'}, '/')
>>> check_response_for_credentials({'test': {'authKey': 'x'}}, '/')  # doctest: +ELLIPSIS
Traceback (most recent call last):
    ...
RuntimeError...test...authKey...
>>> check_response_for_credentials({'test': [{'token': 'x'}]}, '/')  # doctest: +ELLIPSIS
Traceback (most recent call last):
    ...
RuntimeError...test...0...token...
>>> check_response_for_credentials({'test': 1, 'passwd': 'x'}, '/')  # doctest: +ELLIPSIS
Traceback (most recent call last):
    ...
RuntimeError...passwd...
>>> check_response_for_credentials({'password': 'x'}, '/')  # doctest: +ELLIPSIS
Traceback (most recent call last):
    ...
RuntimeError...password...
>>> check_response_for_credentials({'a': [{'b': [{'token': 'x'}]}]}, '/')  # doctest: +ELLIPSIS
Traceback (most recent call last):
    ...
RuntimeError...a...b...token...
>>> check_response_for_credentials(
...     {'specificFeatures': {'4_3_fix_typo_in_ldapPasswordExpirationPeriod': 'true'}},
...     'rest/v1/system/settings',
...     )
>>> check_response_for_credentials(
...     {'adminPassword': 'qwe', 'passwordExpirationPeriodMs': 5},
...     'rest/v3/ldap/settings',
...     )
>>> check_response_for_credentials(
...     {'reply': {'settings': {'smtpPassword': 'hjk'}}},
...     'api/systemSettings',
...     )
>>> check_response_for_credentials(
...     {'reply': {'settings': {'emailSettings': {'password': 'hjk'}}}},
...     'api/systemSettings',
...     )
>>> check_response_for_credentials(
...     {'reply': {'settingsValues': {'passwordField1'}}},
...     'ec2/analyticsEngineSettings',
...     )
>>> check_response_for_credentials(
...     {
...         'credentials': {'user': 'booba', 'password': 'hooba'},
...         'parameters': {'availableProfiles': [{'token': 'quluS'}]},
...         },
...     'rest/v1/devices/18-68-CB-43-F3-33',
...     )
>>> check_response_for_credentials(
...     {'credentials': {'user': 'booba', 'password': 'hooba'}},
...     'rest/v1/devices/18-68-CB-43-F3-33_channel=42',
...     )
>>> check_response_for_credentials(
...     {'credentials': {'user': 'booba', 'password': 'hooba'}},
...     'rest/v2/devices/uuid_528d8cbc-ba71-5e70-eb11-922f4e32ba71',
...     )
>>> check_response_for_credentials(
...     {'credentials': {'user': 'booba', 'password': 'hooba'}},
...     'rest/v2/devices/urn_uuid_000a611a-000a-4611-8a10-000a611a101d',
...     )
>>> check_response_for_credentials(
...     [
...         {'dummy': 'one'},
...         {'credentials': {'password': 'qwe'}, 'parameters': {'availableProfiles': [{'token': 'quluS'}]}},
...         ],
...     '/rest/v3/devices',
...     )
>>> check_response_for_credentials(
...     {'credentials': {'password': 'qwe'}},
...     '/rest/v3/devices/{18-68-CB-43-F3-33}',
...     )
>>> check_response_for_credentials(
...     {'credentials': {'password': 'qwe'}},
...     '/rest/v3/devices/*/',
...     )
>>> check_response_for_credentials(
...     {
...         'dummy': 'value',
...         'devices': [
...             {'dummy': 'one'},
...             {'credentials': {'password': 'qwe'}},
...             {'credentials': {'password': 'asd'}},
...             ],
...         },
...     '/rest/v2/devices/*/searches/18-68-CB-43-F3-33',
...     )
>>> check_response_for_credentials(
...     {'credentials': {'password': 'qwe'}},
...     '/rest/v1/devices/*/searches/{d66a9104-a247-11ed-a8fc-0242ac120002}',
...     )
>>> check_response_for_credentials(
...     {'credentials': {'password': 'qwe'}},
...     '/rest/v2/devices/*/searches',
...     )
>>> check_response_for_credentials(
...     {'reply': {'useShowPasswordButton': True}},
...     '/ec2/deviceAnalyticsSettings',
...     )
"""
import re
from abc import ABCMeta
from abc import abstractmethod
from typing import Any
from typing import Collection
from typing import Iterable
from typing import List
from typing import NamedTuple
from typing import Union


class _Field(NamedTuple):

    path: str
    json_selector: str
    value: Any


class _Rule(metaclass=ABCMeta):

    @abstractmethod
    def is_matched(self, packet: _Field) -> bool:
        pass


class _KeyContainsSubstringRule(_Rule):

    def __init__(self, key: str):
        self._key = key.lower()

    def is_matched(self, packet: _Field) -> bool:
        [*_, key] = packet.json_selector.split('.')
        if self._key in key.lower():
            return True
        return False


class _UrlSpecificSelectorMatchRule(_Rule):

    def __init__(self, url_re: str, json_selector_re: str):
        self._url = re.compile(url_re)
        self._selector = re.compile(json_selector_re)

    def is_matched(self, packet: _Field) -> bool:
        if not re.fullmatch(self._url, packet.path):
            return False
        return re.fullmatch(self._selector, packet.json_selector) is not None


class _FullKeyMatchRule(_Rule):

    def __init__(self, key):
        self._key = key

    def is_matched(self, packet: _Field) -> bool:
        [*_, key] = packet.json_selector.split('.')
        return self._key == key


class _EmptyPasswordRule(_Rule):

    def is_matched(self, packet: _Field) -> bool:
        if packet.value is None:
            return True
        if packet.value == '':
            return True
        if isinstance(packet.value, str):
            if packet.value == '*' * len(packet.value):
                return True
        return False


class _JsonSelectorsFilter:

    def __init__(self, white_list: Collection[_Rule], black_list: Collection[_Rule]):
        self._white_list = white_list
        self._black_list = black_list

    def packet_is_ok(self, packet: _Field) -> bool:
        if isinstance(packet.value, bool):
            return True
        for white_list_rule in self._white_list:
            if white_list_rule.is_matched(packet):
                return True
        for black_list_rule in self._black_list:
            if black_list_rule.is_matched(packet):
                return False
        return True

    def get_fields_containing_password(self, packets: Iterable[_Field]) -> Iterable[_Field]:
        result = []
        for packet in packets:
            if self.packet_is_ok(packet):
                continue
            result.append(packet)
        return result


def _flatten_dict(
        path: str,
        data: Union[dict[str, Any], List[Any]],
        current_json_selector: str = '',
        ) -> Iterable[_Field]:
    result = []
    if isinstance(data, dict):
        for [key, value] in data.items():
            json_selector = f'{current_json_selector}.{key}'
            if isinstance(value, (list, dict)):
                result.extend(
                    _flatten_dict(
                        path,
                        value,
                        json_selector,
                        ),
                    )
            else:
                result.append(
                    _Field(
                        path=path,
                        json_selector=json_selector,
                        value=value,
                        ),
                    )
    elif isinstance(data, list):
        for [index, value] in enumerate(data):
            json_selector = current_json_selector + f'[{index}]'
            if isinstance(value, (list, dict)):
                result.extend(
                    _flatten_dict(
                        path,
                        value,
                        json_selector,
                        ),
                    )
            else:
                result.append(
                    _Field(
                        path=path,
                        json_selector=json_selector,
                        value=value,
                        ),
                    )
    else:
        raise RuntimeError(
            f"Can't flatten dict {type(data).__name__}")
    return result


_response_filter = _JsonSelectorsFilter(
    white_list=[
        _EmptyPasswordRule(),
        _FullKeyMatchRule('passwordExpirationPeriodMs'),
        _FullKeyMatchRule('token_type'),
        _FullKeyMatchRule('4_3_fix_typo_in_ldapPasswordExpirationPeriod'),
        _FullKeyMatchRule('ldapPasswordExpirationPeriodMs'),
        _UrlSpecificSelectorMatchRule(
            r'/?api/virtualCamera/(?:lock|status|consume|release)',
            r'\.reply\.token',
            ),
        _UrlSpecificSelectorMatchRule(r'/?api/setupCloudSystem', r'\.reply\.settings\.cloudAuthKey'),
        _UrlSpecificSelectorMatchRule(r'/?cdb/oauth2/token', r'\.refresh_token'),
        _UrlSpecificSelectorMatchRule(r'/?cdb/oauth2/token', r'\.access_token'),
        _UrlSpecificSelectorMatchRule(r'/?rest/v\d/login/sessions', r'\.token'),
        _UrlSpecificSelectorMatchRule(r'/?rest/v\d/login/sessions', r'\[\d+]\.token'),
        _UrlSpecificSelectorMatchRule(r'/?rest/v\d/login/sessions/vms-[\da-f]+-[\dA-Za-z]+', r'\.token'),
        _UrlSpecificSelectorMatchRule(r'/?rest/v\d/login/sessions/nxcdb-[\da-f-]+', r'\.token'),
        _UrlSpecificSelectorMatchRule(r'/?rest/v\d/login/sessions/nxcdb-[\w-]+\.[\w-]+\.[\w-]+', r'\.token'),
        _UrlSpecificSelectorMatchRule(
            r'/?rest/v\d/devices(/\*/)?(/((urn_)?uuid_)?{?[\da-fA-F-]+}?(_channel=\d+)?)?',
            r'(\[\d+])?\.credentials\.password|(\[\d+])?\.parameters\.availableProfiles\[\d+]\.token',
            ),
        _UrlSpecificSelectorMatchRule(
            r'/?rest/v\d/devices/\*/searches(/{?[\da-fA-F-]+}?)?',
            r'((\.devices)?(\[\d+])?)?\.credentials\.password'),
        _UrlSpecificSelectorMatchRule(r'/?rest/v\d/ldap/settings', r'\.adminPassword'),
        _UrlSpecificSelectorMatchRule(r'/?cdb/systems/bind', r'\.authKey'),
        _UrlSpecificSelectorMatchRule(r'/?cdb/systems/bind', r'\.authKeyHash'),
        _UrlSpecificSelectorMatchRule(
            r'/?ec2/analyticsEngineSettings',
            r'\.reply\.settingsValues\.passwordField1',
            ),
        _UrlSpecificSelectorMatchRule(
            r'/?ec2/deviceAnalyticsSettings',
            r'\.reply\.settingsValues\.passwordField1',
            ),
        _UrlSpecificSelectorMatchRule(
            r'/?ec2/notifyAnalyticsEngineActiveSettingChanged',
            r'\.reply\.settingsValues\.passwordField1',
            ),
        _UrlSpecificSelectorMatchRule(
            r'/?ec2/notifyDeviceAnalyticsActiveSettingChanged',
            r'\.reply\.settingsValues\.passwordField1',
            ),
        _UrlSpecificSelectorMatchRule(
            r'/?rest/v\d/analytics/engines/[0-9a-z\-]{36}/deviceAgents/[0-9a-z\-]{36}/settings',
            r'\.values\.passwordField1',
            ),
        _UrlSpecificSelectorMatchRule(
            r'/?rest/v\d/devices/[0-9a-z\-]{36}',
            r'\.parameters\.deviceAgentsSettingsValuesProperty\[0\]\.value\.passwordField1',
            ),
        _UrlSpecificSelectorMatchRule('/?api/systemSettings', r'\.reply\.settings\.ldapAdminPassword'),
        _UrlSpecificSelectorMatchRule('/?api/systemSettings', r'\.reply\.settings\.smtpPassword'),
        _UrlSpecificSelectorMatchRule(
            '/?api/systemSettings', r'\.reply\.settings\.emailSettings\.password',
            ),
        # Should be removed after VMS-47479 fixed
        _UrlSpecificSelectorMatchRule(
            r'/?rest/v\d/system/settings', r'\.emailSettings\.password',
            ),
        _UrlSpecificSelectorMatchRule(
            r'/?rest/v\d/analytics/integrations/\*/requests', r'\.password',
            ),
        _UrlSpecificSelectorMatchRule(
            r'/?cdb/account/createTemporaryCredentials', r'\.password',
            ),
        _UrlSpecificSelectorMatchRule(r'/?partners/api/v2/cloud_systems/', r'\.authKey'),
        _UrlSpecificSelectorMatchRule(r'/?partners/api/v2/cloud_systems/', r'\.authKeyHash'),
        ],
    black_list=[
        _KeyContainsSubstringRule('authkey'),
        _KeyContainsSubstringRule('token'),
        _KeyContainsSubstringRule('password'),
        _KeyContainsSubstringRule('passwd'),
        ],
    )


def check_response_for_credentials(
        response_json: Union[List[Any], dict[str, Any]],
        path: str,
        ):
    fields = _flatten_dict(path, response_json)
    fields_containing_password = _response_filter.get_fields_containing_password(
        fields,
        )
    if fields_containing_password:
        field_list_string = ', '.join(map(str, fields_containing_password))
        raise RuntimeError(
            f"Request contains credentials in fields: {field_list_string}",
            )
