# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
import logging
from functools import lru_cache
from pprint import pformat
from typing import Mapping
from typing import Union
from urllib.parse import quote
from urllib.parse import urlencode

import requests

from doubles.licensing._licensing_server import LicenseServer

from _internal.licensing import _TEST_SERVER_URL, _SERVICE_ACCOUNT

_logger = logging.getLogger(__name__)


@lru_cache(1)
def get_remote_licensing_server() -> '_RemoteLicenseServer':
    return _RemoteLicenseServer()


class _RemoteLicenseServer(LicenseServer):

    def __init__(self):
        url = _TEST_SERVER_URL
        self._url = url
        self._api = ServerApi(url=url)

    def url(self) -> str:
        return self._url

    def generate(self, license_data):
        return self._api.generate(license_data)

    def activate(self, license_key, hardware_id):
        return self._api.activate(license_key, hardware_id)

    def deactivate(self, license_key):
        return self._api.deactivate(license_key)

    def disable(self, license_key):
        return self._api.disable(license_key)

    def info(self, license_key):
        return self._api.info(license_key)


class ApiError(Exception):

    def __init__(self, url, result_code, error_string, json):
        self.url = url
        self.result_code = result_code
        self.error_string = error_string
        self.json = json


class ValidationError(Exception):

    pass


class ServerApi:

    def __init__(self, url=_TEST_SERVER_URL, auth=_SERVICE_ACCOUNT):
        self._base_url = f'{url.rstrip("/")}/nxlicensed'
        self._auth = auth
        self._session = requests.Session()
        self._login()

    def _login(self):
        login_path = 'checklogin.php'
        self._request('GET', login_path)
        self._session.headers.update({'Referer': self._base_url})
        csrftoken = self._csrf_token or 'removeme'
        username, password = self._auth
        data = {
            'email': username,
            'password': password,
            'csrfmiddlewaretoken': csrftoken,
            }
        self._request('POST', login_path, data=data)
        if self._csrf_token:
            self._session.headers.update({'X-CSRFToken': self._csrf_token})

    def _request(self, method, path, params=None, **kwargs):
        params_str = pformat(params, indent=4)
        if '\n' in params_str or len(params_str) > 60:
            params_str = '\n' + params_str
        url = self._base_url + '/' + path
        _logger.debug('GET %s, params: %s', url, params_str)
        if params:
            params = urlencode(params, quote_via=quote).encode('ascii')
        response = self._session.request(
            method,
            url,
            params=params,
            timeout=60,  # Add timeout so call will not hang indefinitely
            **kwargs,
            )
        _logger.debug(
            "Response %s (%s):\n%s",
            response.status_code, response.reason, response.content)
        response.raise_for_status()
        return response

    def _request_json(self, method, path, params=None, **kwargs):
        response = self._request(method, path, params, **kwargs)
        json_data = response.json()
        _logger.debug("JSON response:\n%s", json.dumps(json_data, indent=4))
        result_code = json_data.get('status')
        error_string = json_data.get('message')
        if result_code not in [None, 'ok']:
            raise ApiError(response.request.url, result_code, error_string, json_data)
        return json_data

    @property
    def _csrf_token(self):
        return self._session.cookies.get('csrftoken')

    def deactivate(self, license_keys):
        data = {
            'mode': 'deactivate',
            'license_keys[]': license_keys,
            'autodeact_reason': '1',
            'new_hwid': '',
            'integrator': 'AutoTest Integrator',
            'end_user': 'AutoTest End User',
            }
        try:
            self._request('POST', 'autodeact.php', params={'format': 'json'}, data=data)
        except requests.exceptions.HTTPError as exc:
            # `deactivate` validation error processing.
            # Licensing server returns validation error in JSON body with
            # 503 `Service Unavailable` status HTTP-status.
            json_data = exc.response.json()
            if exc.response.status_code == 503 and 'validation error' in json_data['message'].lower():
                raise ValidationError()
            raise RuntimeError('Unexpected deactivation response')

    def generate(self, license_data: Mapping[str, Union[str, float]]):
        """Generate license key."""
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
            **license_data,
            }
        response = self._request_json('POST', 'genkey.php', data=data)
        return response['items'][0]['key']

    def disable(self, license_key):
        data = {
            'license_key': license_key,
            }
        return self._request_json('POST', 'api/v1/licenses/disable/', data=data)

    def info(self, license_key):
        return self._request_json('GET', 'api/v1/licenses/info/', params={'license_key': license_key})

    def activate(self, license_key, hardware_id):
        data = {
            'oldhwid[]': 'The license is activated by hand',
            'manual': '1',
            'license_key': license_key,
            'hwid[]': hardware_id,
            }
        response = self._request('POST', 'activation/', data=data)
        response.raise_for_status()
        return response.content.decode()
